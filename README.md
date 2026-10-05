# MovieGraph：电影知识图谱与可解释推荐系统

完整前后端课程项目。**Streamlit 前端 + FastAPI 后端 + Neo4j 图数据库**，数据使用 MovieLens Latest Small 的 `movies.csv` 和 `tags.csv`。

## 本机立即启动

双击项目目录中的 **`start.bat`**，随后浏览器自动打开：

- 应用：http://127.0.0.1:18501
- 后端接口文档：http://127.0.0.1:18080/docs
- Neo4j Browser：http://127.0.0.1:17474 （本地专用实例，无需密码）

本机已准备 Python 虚拟环境、便携 Java 21、Neo4j 5.26 和真实数据。正常启动不需要联网。保持整个 MovieGraph 文件夹完整。关闭网页不会停止后台服务；双击 `stop.bat` 关闭本项目服务。

## 三个核心功能

1. **电影查询**：英文原始标题的部分匹配、不区分大小写、结果分页，电影显示独立 movieId，支持重名。
2. **局部图谱**：当前电影、类型、标签、最多 12 部相关电影。点击类型/标签显示关联电影列表，点击电影切换中心。支持拖动、缩放、键盘按钮替代操作。
3. **可解释推荐**：共享类型数量 + 共享标签数量，返回最多 5 部其他电影。逐项展示共同类型、标签和分数拆解。同分按 movieId 升序，无标签时按类型推荐，无共同关系时明确提示。

当前数据：9,742 部电影、19 个真实类型、1,475 个清洗后独立标签、25,624 条关系。`(no genres listed)` 表示缺失，未创建成类型节点。来源中的评分、链接信息未加入业务。

## 目录

```text
MovieGraph/
  start.bat / stop.bat / rebuild.bat / test.bat
  backend/                 FastAPI 接口、参数化 Cypher 查询
  frontend/                Streamlit 页面、离线可用图谱组件
  scripts/                 获取清洗、导入、启动、测试及演示程序
  data/raw/                原始 movies.csv、tags.csv、来源 README 和下载包
  data/processed/          清洗数据、关系表、统计及数据版本指纹
  docs/                    原分工、接口、方法、讲稿、测试记录
  deliverables/            项目 PPT、论文 PPT、截图、演示视频
  runtime/                 便携 Java 和 Neo4j（无需安装系统服务）
  logs/                    服务日志和本项目进程登记
  requirements.txt         应用直接依赖版本
  requirements-dev.txt     浏览器测试/视频工具依赖
```

## 从原始数据重新生成图谱

双击 `rebuild.bat`，或在项目目录运行：

```powershell
.\.venv\Scripts\python.exe scripts\prepare_data.py
.\.venv\Scripts\python.exe scripts\import_graph.py
```

先确保 Neo4j 已启动。清洗脚本从保留的原始下载包提取两张 CSV，不依赖手工修改的中间产物。导入程序建立唯一约束，使用 MERGE，重复执行不增加重复实体或关系。数据按清洗结果 SHA-256 前 20 位分版本，只有导入数量验证通过才切换当前版本。旧版本保留，不删除其他图数据。

## 换电脑运行

Windows 10/11，Python 3.11 或更高，建议至少 4 GB 空闲内存。复制源代码包后运行 `start.bat`，首次自动建立 `.venv`、安装依赖、下载 Java 和 Neo4j、处理数据并导入。首次需要网络，下载量约 300 MB 以上。源代码包不含本机不可移植的 `.venv` 和运行中的数据库文件。

如自行部署 Neo4j，可设置 `NEO4J_URI`、`NEO4J_USER`、`NEO4J_PASSWORD`、`NEO4J_DATABASE` 后运行。默认端口分别为 17687、17474、18080、18501，避免占用常用端口。运行环境只监听 `127.0.0.1`，用于本地课程演示，未配置远程部署的登录、TLS 和访问控制。

如果 `start.bat` 提示 Python 缺失，安装 Python 并勾选 Add Python to PATH。若环境文件损坏，在本项目目录重新创建虚拟环境并执行 `pip install -r requirements.txt`。更换电脑不要直接复制旧虚拟环境。错误信息见 `logs/backend.log`、`logs/frontend.log`，数据库详细日志见 `runtime/neo4j-community-5.26.0/logs/neo4j.log`。

## 检验和提交

运行 `test.bat` 执行真实数据库与 API 验收。`scripts/browser_check.py` 需要开发依赖和 Chrome，验证图谱点击、推荐导航、搜索和统计页面。记录见 [测试记录](docs/测试记录.md)。

- [原分工与任务详情](docs/原分工与任务详情.md)
- [架构与接口说明](docs/架构与接口.md)
- [数据来源、清洗规则及使用条件](docs/数据说明.md)
- [项目演示讲稿](docs/项目演示讲稿.md)
- [TransE 论文讲稿与问答](docs/论文讲稿与问答.md)

系统实现的是基础图关系推荐，未训练 TransE、未加入评分或用户画像。论文 PPT 中的指标均来自原论文，明确区分论文结果和本项目验收结果。课堂是否要求复现论文、汇报时长及论文年份限制，原任务未给出确定答案。

