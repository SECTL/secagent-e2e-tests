# SecAgent 端到端评测（E2E Tests）

用 pytest 驱动 **SecAgent CLI**，对已接入 SecAgent 的各类电教软件做端到端任务评测：
模型拿到一句自然语言指令（如"下节课是啥"），通过联动插件真实操作目标软件，
评测框架负责拉起被测实例、隔离数据、控制超时、收集模型的完整执行过程，
最后把"过程 + 标准答案"交给 **deepseek 裁判** 判定是否真正做对。

当前内置 **ClassIsland（课表）** 的 8 个用例；未来可扩展 ICC-CE、SecScore 等系统的用例。

## 工作原理

每个用例执行一次完整闭环：

```
pytest 用例
  ├─ setup.py：构建独立测试 workspace（复制登录态 .env + 注入新版 connector）
  ├─ 生成"增强备份 zip"：修复备份档案文件名（UTF-8）并注入 ClassIsland 侧联动插件
  ├─ 启动测试版 ClassIsland：
  │     ClassIsland.exe --backupZip <zip> --simulateTime 2026-08-05T10:30:00 --skip-oobe --quiet
  │     （独立端口 18799 + 独立单实例锁，与正在运行的正式版互不干扰）
  ├─ 等待联动服务 http://127.0.0.1:18799/health 就绪
  ├─ 调用 SecAgent CLI：
  │     node dist/index.js run "<任务>" --workspace <测试workspace> --model <模型>
  │     （60 秒超时即杀掉；模型端点网络波动自动重试 3 次）
  └─ 收集过程到 results/<case_id>/：cli_stdout.txt、runtime.jsonl、session.json、summary.json
```

**为什么用独立 workspace**：正在运行的 SecAgent 桌面端共享 `~/SecAgentWorkspace`
并会把已安装的 connector 插件还原成它缓存的旧版；测试使用该目录的**副本**
（含 `.env` 登录态），桌面端管不到，二者互不干扰。

## 目录结构

```
secagent-e2e-tests/
├── eval_config.py      # 配置（路径/模型/超时/模拟时间，全部可用环境变量覆盖）
├── eval_cases.py       # 8 个用例定义 + 标准答案
├── ci_harness.py       # 增强 zip 生成、ClassIsland 实例启停、健康检查
├── run_case.py         # 单用例执行：启动 CI → 跑 CLI → 收集过程（含重试）
├── test_eval.py        # pytest 用例（链路断言：60s 内完成、有工具调用、过程落盘）
├── conftest.py         # session 级 setup + 临时目录清理
├── setup.py            # 构建独立测试 workspace（登录态 + 新版 connector）
├── judge_prompt.py     # deepseek 裁判提示词（标准答案 + 过程判定规则）
├── judge.py            # 裁判客户端：把执行过程发给 deepseek 评分
├── run_eval.py         # 一键入口：pytest + 结果摘要
└── requirements.txt
```

## 环境要求

| 组件 | 说明 |
|------|------|
| Python 3.10+ | `python -m venv .venv && .venv/Scripts/pip install -r requirements.txt` |
| Node.js 18+ | SecAgent CLI 运行环境（`D:\Code\SecAgentAll\SecAgent\dist\index.js`） |
| 测试版 ClassIsland | 支持 `--backupZip/--dataPath/--simulateTime` 参数的分支构建（feature/secagent-autotest） |
| ClassIsland 联动插件 | 新版（支持 `CLASSISLAND_CONNECTOR_URL` 环境变量端口、模拟时钟）构建产物目录 |
| SecAgent 侧 connector | 支持 `CLASSISLAND_CONNECTOR_URL` 的 `main.mjs`（会被注入测试 workspace） |
| SecAgent 工作区登录态 | `~/SecAgentWorkspace/.env`（API key）与 `secagent.yaml`（模型配置） |
| 备份数据 zip | 被测档案快照（Settings.json + Profiles/...） |

## 快速开始

```bash
# 1. 安装依赖
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt

# 2. 配置（均可用环境变量覆盖，默认值见 eval_config.py / setup.py）
set CLASSISLAND_EXE=D:\path\to\ClassIsland.Desktop.exe      # 测试版 exe（必须支持新参数）
set BACKUP_ZIP=D:\path\to\Backup_ForTest1.zip               # 备份数据 zip
set PLUGIN_DIR=D:\path\to\ClassIsland-SecAgent-Plugin\bin\TestBuild
set CONNECTOR_SRC=D:\path\to\ClassIsland-SecAgent-Connector # setup.py 用
set SECAGENT_ROOT=D:\path\to\SecAgent                        # SecAgent CLI 仓库
set SECAGENT_MODEL_ID=sectl-official:deepseek-v4-flash       # "快速"档模型
set CI_PORT=18799                                            # 测试实例服务端口（避开正式版 18789）
set SIMULATE_TIME=2026-08-05T10:30:00                        # 模拟启动时间

# 3. 跑全部用例（每个最多 60 秒，约 5 分钟）
.venv/Scripts/python run_eval.py
# 或
.venv/Scripts/python -m pytest test_eval.py -v

# 4. 裁判评分（需要 deepseek key 和端点）
set JUDGE_API_KEY=sk-xxx
set JUDGE_BASE_URL=https://api.deepseek.com/v1
set JUDGE_MODEL=deepseek-reasoner
.venv/Scripts/python judge.py          # 输出 results/judge_report.json
```

## 测试用例说明

模拟时间：**2026-08-05（周三）10:30**，第 3 节（10:10–10:55）上课中。
"这周日"= 2026-08-09，"明天"= 2026-08-06（周四）。

档案课表（课程表.json）：
- 周一：语文、数学、英语、物理、历史、生物、体育与健康
- 周二：数学、语文、英语、道德与法治、物理、地理、音乐
- 周三：英语、数学、物理、历史、生物、体育与健康、信息技术
- 周四：数学、语文、英语、物理、地理、化学/科学、劳动技术
- 周五：语文、数学、英语、体育与健康、道德与法治、美术、班会

节次：第1节 08:00–08:45 / 第2节 08:55–09:40 / 第3节 10:10–10:55 / 第4节 11:05–11:50 /
第5节(下午1) 14:00–14:45 / 第6节(下午2) 14:55–15:40 / 第7节(下午3) 15:50–16:35。

| id | 任务 | 标准答案 | 判定要点 |
|----|------|----------|----------|
| swap_am3_pm1 | 上午第三节跟下午第一节换了 | 周三第3节 物理↔第5节 生物 | 必须调用写档案工具且参数正确，最好重查验证 |
| sunday_use_monday | 这周日调休上周一的课，调一下课表 | 周日(08-09)课表改为周一 7 节 | 为周日建立/关联周一课表 |
| next_lesson | 下节课是啥 | 第4节 历史（11:05–11:50） | 查课表工具 + 用返回的 now 判断当前节次 |
| pm1_lesson | 下午第一节是啥 | 第5节 生物 | 查课表工具 |
| tomorrow_this_lesson | 明天这节是啥课 | 周四第3节 英语 | 查今天+明天课表 |
| math_period | 今天第几节数学 | 第2节 | 查课表工具 |
| ci_delay | 调一下ci延迟，铃声慢了5秒 | TimeOffsetSeconds 0 → -5（减小偏移抵消铃声滞后） | 必须调用主配置更新工具 |
| ci_ui_bigger | ci主界面调大一点 | 主界面组件字号调大（如 MainWindowBodyFontSize 16→≥18） | 必须调用组件更新工具 |

> 时间说明：评测里 ClassIsland 以模拟时间启动，"当前时刻"以插件工具返回的
> `now` / `now_local` / `localDateTime` 为准（connector 的 SKILL 已注明禁止用
> bash 的 `date` 命令，那会拿到真实系统时间）。

## 裁判（judge）

`judge.py` 把每个用例的 `runtime.jsonl`（模型思考 + 工具调用 + 返回结果）与
`cli_stdout.txt` 拼成提示词发给 deepseek。提示词包含：

1. 环境背景（模拟时间、课表、时间表、工具清单）
2. 每个用例的标准答案（预期结果 + 预期过程）
3. 判定方法论：
   - 结果正确性：最终回答/修改后的状态与标准答案一致
   - 过程真实性：查询类必须调用查询工具，修改类必须调用对应写工具且参数正确
   - "真正改对 vs 口头答应"：工具失败/未执行写操作/参数不符 = 未真正改对
   - 编造检测：声称的结果与工具返回不一致 = 编造
   - 修改后重新查询验证是过程正确的有力证据

输出 JSON 数组，每项 `{case_id, pass: pass|partial|fail, result_correct, process_correct, evidence, reason}`。

## 已知限制

- 用例彼此独立（每个用例重新解压备份 zip、全新会话），不测跨用例状态累积。
- 修改类用例"真正改对"以裁判判定为准，pytest 只保证执行链路成功。
- 60 秒超时对复杂任务（如调休换课）可能偏紧，可在 `CASE_TIMEOUT_SEC` 调大。
- 模型质量直接影响通过率：快速档（flash）在复杂推理任务上容易绕圈/超时。
