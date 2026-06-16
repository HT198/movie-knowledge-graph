import streamlit as st
import pandas as pd
from neo4j import GraphDatabase
import requests
import json

# ==================== 配置区域 ====================
# Neo4j 配置
NEO4J_URI = "neo4j+s://b865f65c.databases.neo4j.io"
NEO4J_USERNAME = "b865f65c"
NEO4J_PASSWORD = "bkeW9iMYQE0XYVoYBXukRlRZj4UCOprSgp-1F5fvmiM"
NEO4J_DATABASE = "b865f65c"

# 大模型 API 配置
DEEPSEEK_API_KEY = "sk-ws-H.REEPIDY.GfI4.MEQCIH0Qd0Nl2XOe9BoVz1iy6SMgKGuKTOrpsj24j-mJrpZMAiAY9QE3wXaKNklwHPXg3w4Kv4fCBxO7cvcW9qbt-i9z9Q"
DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"

# ==================== 初始化 Neo4j 连接 ====================
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

# ==================== 10条查询语句（你提供的） ====================
queries = {
    "1. 统计影片、导演、创作关系总数量": """
MATCH (m:Movie),(d:Director),(d)-[r:CREATE]->(m)
RETURN count(DISTINCT m) AS 影片总量,count(DISTINCT d) AS 导演总量,count(DISTINCT r) AS 创作关系总量
""",
    "2. 查询全部导演名单（去重排序）": """
MATCH (d:Director)
RETURN DISTINCT d.director_name AS 导演姓名
ORDER BY 导演姓名
""",
    "3. 查询James Cameron所有影片及评分、年份": """
MATCH (d:Director{director_name:"James Cameron"})-[:CREATE]->(m:Movie)
RETURN m.name AS 影片名,m.year AS 上映年份,m.rating AS 评分
ORDER BY m.rating DESC
""",
    "4. 统计每位导演执导影片数量": """
MATCH (d:Director)-[:CREATE]->(m:Movie)
RETURN d.director_name AS 导演,count(m) AS 执导影片数
ORDER BY count(m) DESC
""",
    "5. 查询评分大于9分的高分影片及对应导演": """
MATCH (d:Director)-[:CREATE]->(m:Movie)
WHERE m.rating > 9
RETURN m.name AS 高分影片,m.rating AS 评分,d.director_name AS 导演
ORDER BY m.rating DESC
""",
    "6. 查询2020年及之后上映的全部电影": """
MATCH (d:Director)-[:CREATE]->(m:Movie)
WHERE m.year >= 2020
RETURN m.name,m.year,m.rating,d.director_name
ORDER BY m.year DESC
""",
    "7. 查询6~8分中等评分影片（限制20条）": """
MATCH (m:Movie)
WHERE m.rating >=6 AND m.rating <=8
RETURN m.name,m.rating,m.year LIMIT 20
""",
    "8. 评分最高的前10部电影": """
MATCH (d:Director)-[:CREATE]->(m:Movie)
RETURN m.name,m.rating,d.director_name
ORDER BY m.rating DESC LIMIT 10
""",
    "9. 按年份统计每年上映影片总数": """
MATCH (m:Movie)
RETURN m.year AS 年份,count(m) AS 影片数量
ORDER BY m.year
""",
    "10. 2010年后高分且执导≥3部影片的导演": """
MATCH (d:Director)-[:CREATE]->(m:Movie)
WHERE m.year>2010 AND m.rating>8.5
WITH d, collect(m) AS movie_list WHERE size(movie_list)>=3
UNWIND movie_list AS single_movie
RETURN d.director_name AS 导演, single_movie.name AS 影片名称
ORDER BY d.director_name
"""
}

# ==================== 大模型问答功能 ====================
def natural_language_to_cypher(question):
    system_prompt = """你是一个Neo4j Cypher查询生成专家。数据库中有两种节点：
- Movie: 电影，属性有 name(片名), year(年份), rating(评分)
- Director: 导演，属性有 director_name(导演姓名)
关系: (Director)-[:CREATE]->(Movie)

请将用户的问题转换为Cypher查询语句，只返回Cypher代码，不要有其他解释。"""
    
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
            
            # 如果查询结果包含年份和数量，显示图表
            if "年份" in df.columns and "影片数量" in df.columns:
                st.bar_chart(df.set_index("年份"))
        else:
            st.info("ℹ️ 查询无返回数据")
    except Exception as e:
        st.error(f"❌ 查询失败: {str(e)}")

st.sidebar.markdown("---")

# 自然语言问答
st.sidebar.header("🤖 智能问答（加分项）")
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

# 主区域：全局实体检索
st.subheader("🔍 全局实体模糊检索（影片/导演）")
keyword = st.text_input("输入名称关键字检索：", placeholder="例如：Cameron、阿凡达")

if keyword:
    # 使用参数化查询防止注入
    search_cypher = """
    MATCH (n)
    WHERE (n.name IS NOT NULL AND n.name CONTAINS $keyword) 
       OR (n.director_name IS NOT NULL AND n.director_name CONTAINS $keyword)
    RETURN labels(n)[0] AS 实体类型, coalesce(n.name, n.director_name) AS 实体名称
    LIMIT 50
    """
    try:
        with driver.session(database=NEO4J_DATABASE) as sess:
            result = sess.run(search_cypher, keyword=keyword)
            data = [row.data() for row in result]
        if data:
            st.dataframe(pd.DataFrame(data), use_container_width=True)
        else:
            st.info(f"未找到包含 '{keyword}' 的实体")
    except Exception as err:
        st.error(f"检索异常：{err}")

# 自定义Cypher执行区
st.markdown("---")
st.subheader("📝 自定义Cypher语句执行")
user_cypher = st.text_area("在此输入Cypher查询代码：", height=120, 
                           placeholder="示例: MATCH (m:Movie) RETURN m.name, m.rating LIMIT 5")
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

# 页脚
st.markdown("---")
st.info("""
📌 **系统说明**：
- 左侧为10个预设Cypher查询（使用 :CREATE 关系）
- 智能问答使用DeepSeek API将自然语言转换为Cypher
- 支持全局模糊检索（影片/导演名称）
- 数据存储于Neo4j Aura云端
""")