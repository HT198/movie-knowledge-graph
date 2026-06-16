import streamlit as st
import pandas as pd
from neo4j import GraphDatabase
import requests
import json

# ==================== 配置区域 ====================
# 优先使用 st.secrets（云端），如果没有则使用硬编码（本地）
try:
    NEO4J_URI = st.secrets["NEO4J_URI"]
    NEO4J_USERNAME = st.secrets["NEO4J_USERNAME"]
    NEO4J_PASSWORD = st.secrets["NEO4J_PASSWORD"]
    NEO4J_DATABASE = st.secrets["NEO4J_DATABASE"]
    DEEPSEEK_API_KEY = st.secrets["DEEPSEEK_API_KEY"]
except:
    # 本地开发使用硬编码（修正拼写错误）
    NEO4J_URI = "neo4j+s://b865f65c.databases.neo4j.io"
    NEO4J_USERNAME = "b865f65c"
    NEO4J_PASSWORD = "bkeW9iMYQE0XYVoYBXukR1RZJ4UCOprSgp-1F5fvmIM"
    NEO4J_DATABASE = "b865f65c"
    DEEPSEEK_API_KEY = "sk-ws-H.REEPIDY.GfI4.MQECIHQ0d0N12X0e9BoVz1iy65MgKuGkTOrpsj24j-mJrpZMAiAY9QE3wXaKNk1wHPXg3w4Kv4fCBx07cvvcW9qbt-j9z90"

DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"

# ==================== 初始化 Neo4j ====================
@st.cache_resource
def init_driver():
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USERNAME, NEO4J_PASSWORD))
    with driver.session(database=NEO4J_DATABASE) as session:
        session.run("RETURN 1")
    return driver

try:
    driver = init_driver()
    st.sidebar.success("✅ 数据库连接成功")
except Exception as e:
    st.sidebar.error(f"❌ 数据库连接失败: {str(e)}")
    st.stop()

# ==================== 10条查询语句 ====================
queries = {
    "1. 统计影片、导演、创作关系总数量": """
MATCH (m:Movie)
WITH count(m) AS movie_count
MATCH ()-[r:CREATE]->()
WITH movie_count, count(DISTINCT r.director_name) AS director_count, count(r) AS relation_count
RETURN movie_count AS 影片总量, director_count AS 导演总量, relation_count AS 创作关系总量
""",
    "2. 查询全部导演名单（去重排序）": """
MATCH ()-[r:CREATE]->()
RETURN DISTINCT r.director_name AS 导演姓名
ORDER BY 导演姓名
""",
    "3. 查询James Cameron所有影片及评分、年份": """
MATCH ()-[r:CREATE {director_name: "James Cameron"}]->(m:Movie)
RETURN m.name AS 影片名, m.year AS 上映年份, m.rating AS 评分
ORDER BY m.rating DESC
""",
    "4. 统计每位导演执导影片数量": """
MATCH ()-[r:CREATE]->(m:Movie)
RETURN r.director_name AS 导演, count(m) AS 执导影片数
ORDER BY 执导影片数 DESC
""",
    "5. 查询评分大于9分的高分影片及对应导演": """
MATCH ()-[r:CREATE]->(m:Movie)
WHERE m.rating > 9
RETURN m.name AS 高分影片, m.rating AS 评分, r.director_name AS 导演
ORDER BY m.rating DESC
""",
    "6. 查询2020年及之后上映的全部电影": """
MATCH ()-[r:CREATE]->(m:Movie)
WHERE m.year >= 2020
RETURN m.name AS 电影名, m.year AS 年份, m.rating AS 评分, r.director_name AS 导演
ORDER BY m.year DESC
""",
    "7. 查询6~8分中等评分影片（限制20条）": """
MATCH (m:Movie)
WHERE m.rating >= 6 AND m.rating <= 8
RETURN m.name AS 电影名, m.rating AS 评分, m.year AS 年份
ORDER BY m.rating DESC
LIMIT 20
""",
    "8. 评分最高的前10部电影": """
MATCH ()-[r:CREATE]->(m:Movie)
RETURN m.name AS 电影名, m.rating AS 评分, r.director_name AS 导演
ORDER BY m.rating DESC
LIMIT 10
""",
    "9. 按年份统计每年上映影片总数": """
MATCH (m:Movie)
WHERE m.year IS NOT NULL
RETURN m.year AS 年份, count(m) AS 影片数量
ORDER BY 年份
""",
    "10. 2010年后高分且执导≥3部影片的导演": """
MATCH ()-[r:CREATE]->(m:Movie)
WHERE m.year > 2010 AND m.rating > 8.5
WITH r.director_name AS 导演, collect(m) AS movie_list
WHERE size(movie_list) >= 3
UNWIND movie_list AS single_movie
RETURN 导演, single_movie.name AS 影片名称
ORDER BY 导演
"""
}

# ==================== 大模型问答 ====================
def natural_language_to_cypher(question):
    system_prompt = """你是一个Neo4j Cypher查询生成专家。数据库结构如下：
- 节点类型: Movie (属性: name, year, rating)
- 关系类型: CREATE (属性: director_name，表示导演名字)
- 关系方向: ()-[r:CREATE]->(m:Movie)

请将用户问题转换为Cypher查询，只返回Cypher代码。"""
    
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"用户问题：{question}\n请生成Cypher查询："}
        ],
        "temperature": 0.1
    }
    
    try:
        response = requests.post(DEEPSEEK_API_URL, headers=headers, json=payload, timeout=10)
        if response.status_code == 200:
            result = response.json()
            cypher_query = result['choices'][0]['message']['content']
            cypher_query = cypher_query.replace('```cypher', '').replace('```', '').strip()
            return cypher_query
        return None
    except Exception:
        return None

# ==================== Streamlit UI ====================
st.set_page_config(page_title="影视知识图谱查询系统", layout="wide")
st.title("🎬 影视知识图谱交互查询系统")
st.markdown("基于 Neo4j Aura + DeepSeek API 的智能问答系统")

# 侧边栏：预设查询
st.sidebar.header("⚡ 快速预设查询")
selected_query = st.sidebar.selectbox("选择查询语句", list(queries.keys()))
selected_cypher = queries[selected_query]

with st.sidebar.expander("📄 查看当前Cypher源码"):
    st.code(selected_cypher, language="cypher")

if st.sidebar.button("▶️ 执行查询", type="primary", use_container_width=True):
    try:
        with driver.session(database=NEO4J_DATABASE) as session:
            result = session.run(selected_cypher)
            records = [record.data() for record in result]
        
        if records:
            df = pd.DataFrame(records)
            st.success(f"✅ 查询成功，返回 {len(records)} 条记录")
            st.dataframe(df, use_container_width=True)
        else:
            st.info("ℹ️ 查询无返回数据")
    except Exception as e:
        st.error(f"❌ 查询失败: {str(e)}")

st.sidebar.markdown("---")

# 智能问答
st.sidebar.header("🤖 智能问答")
user_question = st.sidebar.text_input("💬 输入你的问题", placeholder="例如：James Cameron导演过哪些电影？")
if st.sidebar.button("✨ 智能查询", type="secondary", use_container_width=True):
    if user_question:
        with st.spinner("🤔 AI正在理解你的问题..."):
            cypher = natural_language_to_cypher(user_question)
        
        if cypher:
            st.sidebar.code(cypher, language="cypher")
            try:
                with driver.session(database=NEO4J_DATABASE) as session:
                    result = session.run(cypher)
                    records = [record.data() for record in result]
                if records:
                    st.sidebar.success(f"✅ 找到 {len(records)} 条结果")
                    st.sidebar.dataframe(pd.DataFrame(records), use_container_width=True)
                else:
                    st.sidebar.info("未找到相关结果")
            except Exception as e:
                st.sidebar.error(f"查询执行失败: {str(e)}")
        else:
            st.sidebar.error("AI生成Cypher失败")
    else:
        st.sidebar.warning("请输入问题")

# 全局检索
st.subheader("🔍 全局实体模糊检索（影片/导演）")

col1, col2 = st.columns(2)

with col1:
    movie_keyword = st.text_input("搜索电影", placeholder="输入电影名称...")
    if movie_keyword:
        cypher = f"MATCH (m:Movie) WHERE m.name CONTAINS '{movie_keyword}' RETURN m.name AS 电影名, m.year AS 年份, m.rating AS 评分 LIMIT 20"
        try:
            with driver.session(database=NEO4J_DATABASE) as session:
                result = session.run(cypher)
                records = [record.data() for record in result]
            if records:
                st.dataframe(pd.DataFrame(records), use_container_width=True)
            else:
                st.info(f"未找到包含 '{movie_keyword}' 的电影")
        except Exception as e:
            st.error(f"查询失败: {e}")

with col2:
    director_keyword = st.text_input("搜索导演", placeholder="输入导演名称...")
    if director_keyword:
        cypher = f"MATCH ()-[r:CREATE]->() WHERE r.director_name CONTAINS '{director_keyword}' RETURN DISTINCT r.director_name AS 导演名 LIMIT 20"
        try:
            with driver.session(database=NEO4J_DATABASE) as session:
                result = session.run(cypher)
                records = [record.data() for record in result]
            if records:
                st.dataframe(pd.DataFrame(records), use_container_width=True)
            else:
                st.info(f"未找到包含 '{director_keyword}' 的导演")
        except Exception as e:
            st.error(f"查询失败: {e}")

# 自定义Cypher
st.markdown("---")
st.subheader("📝 自定义Cypher语句执行")
user_cypher = st.text_area("在此输入Cypher查询代码：", height=120)
if st.button("执行自定义语句", type="primary"):
    if user_cypher.strip():
        try:
            with driver.session(database=NEO4J_DATABASE) as session:
                result = session.run(user_cypher)
                records = [record.data() for record in result]
            if records:
                st.success(f"✅ 执行成功，返回 {len(records)} 条记录")
                st.dataframe(pd.DataFrame(records), use_container_width=True)
            else:
                st.info("查询无返回数据")
        except Exception as e:
            st.error(f"语法错误: {e}")
    else:
        st.warning("请输入Cypher语句")

st.markdown("---")
st.info("📌 基于 Neo4j Aura + DeepSeek API 的影视知识图谱查询系统")
