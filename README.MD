# 标签自动化项目需求

> 本文档用于记录项目目标、范围、功能需求和验收标准。带有“待填写”或“待确认”的内容需要结合实际业务补充。

你想做的事	访问地址
打开网页/登录系统	http://localhost:5173/login ✅
测试后端 API	http://localhost:8000/api/
Django 管理后台	http://localhost:8000/admin/
http://192.168.20.164:5173/

## 环境说明（重要）
- 后端：Django 6.1.1（不是 5.x，请用 6.1 语法）+ Django REST Framework + SimpleJWT
- 项目根目录：D:\DELTA\label_automation\backend
- 已创建应用：accounts（用户与部门）、workflow（传签流程）
- 数据库：开发阶段用 SQLite（已配置好），后期切 SQL Server
- 前端：Vue 3 + Vite + Element Plus + Pinia + Vue Router + Axios
- 认证：JWT（自己管理用户名密码，暂不接 LDAP）
- 依赖已装齐：djangorestframework、djangorestframework-simplejwt、django-cors-headers


## 业务背景
公司内部传签审批系统，涉及 5 个部门、几十名人员。核心是“装箱单 → Label 申请表 → 多部门审批 → 收尾归档”的流程流转。

## 部门（5个）
1. 业务端（Business）
2. Label室（Label Room）
3. 品管（QC）
4. IE（制造，IE Manufacturing）
5. 工程（Engineering）

## 部门内部结构
每个部门有多个主管（supervisor），每个主管下面有多个下属职员（staff）。
- 部门内的层级：部门 → 主管 → 下属职员
- 主管有额外权限：
  - 可以看到本部门所有待办（不只是指定给自己的）
  - 可以代下属处理审批（在审批界面可以选择“代处理”，记录实际操作人）
- 指定下一环节处理人时，直接选到具体某个人（主管或职员都可以）
- 主管本身也可以作为处理人

## 国际化（i18n）需求
前端支持中英文两种语言：
- 默认语言：英文（en）
- 用户可自行切换（顶部栏放语言切换按钮 EN / 中文）
- 切换后立即生效，刷新后保持用户选择
- 语言偏好存储在 localStorage
- 所有界面文字（菜单、按钮、表单标签、提示、状态名、部门名）都要走 i18n
- 用 vue-i18n 实现，语言包目录：frontend/src/locales/，包含 en.js 和 zh.js
- 部门名也支持中英双语（后端 Department 模型带 name 和 name_zh 字段）
后端
后端不翻译枚举值，接口统一返回英文枚举值（如 pending、processing、completed、supervisor、staff）
由前端用 i18n 把枚举值翻译成对应语言显示。切换语言时不需要重新请求接口
部门名同时返回中英两个字段：
接口返回 { "name": "Label Room", "name_zh": "Label室" }
前端按当前语言选一个显示，切换语言立即生效
错误提示信息（如校验失败、权限不足）也要支持中英文：
后端用 Django 的 gettext_lazy 包一层，按 Accept-Language 返回
前端 axios 拦截器统一加 Accept-Language 请求头，值取自用户当前语言设置

## 完整流程
业务端上传装箱单(PACKING LIST)
    ↓
Label室填写LABEL列印申请表
  - 勾选“是否新机种变更”（New Machine Type）
  - 勾选时，指定下一环节【工程】处理人
  - 未勾选时，指定下一环节【品管】处理人
    ↓
【仅新机种变更时】工程工程师审批
  - 指定下一环节品管处理人
    ↓
品管工程师审批
  - 指定下一环节IE处理人
    ↓
IE(制造)审批
  - 审批通过后，指定Label室收尾处理人
    ↓
Label室收尾（归档/确认）
    ↓
流程结束

未勾选新机种变更时：
业务端 → Label室填表 → 品管 → IE → 传回Label室收尾 → 结束

## 关键业务规则
1. 动态指定处理人：每一环节完成后，当前处理人必须从下一部门的人员列表中指定具体处理人，流程才流转到下一环节。
2. 新机种变更标记：由Label室在填写申请表时勾选。
   - 勾选：流程经过工程审批，Label室填表时需指定工程处理人。
   - 未勾选：Label室填表时需指定品管处理人，流程跳过工程。
3. 工程审批通过后，由工程审批人指定品管处理人。
4. 品管审批通过后，由品管审批人指定IE处理人。
5. IE审批通过后，由IE审批人指定Label室收尾处理人。
6. 驳回：审批不通过时，由不通过的人选择打回到前面任意一个已完成的部门重新处理，需填写驳回理由。
7. 流程状态：待处理、处理中、待收尾、已完成、已驳回。
8. 权限隔离：每个用户只能看到与自己相关的流程。
9. 主管额外权限：
   - 可查看本部门所有待办（不限于指定给自己的）
   - 可代下属处理审批，操作时记录实际处理人和被代理人

## 数据模型

### accounts 应用
- Department：部门表
  - name（英文名）
  - name_zh（中文名）
  - code（部门代码）

- UserProfile：OneToOne 关联 Django User
  - department（FK Department，所属部门）
  - display_name（显示名）
  - role（CharField，choices：supervisor/staff）
  - supervisor（FK User，自关联，职员对应的主管，主管此字段为空）
  - 用户通过 Group 批量分配权限

### workflow 应用
- PackingList（装箱单）
  - uploader（FK User，上传人）
  - file（FileField，文件）
  - machine_type（CharField，机种）
  - order_no（CharField，单号）
  - created_at（DateTimeField）
  - status（CharField）

- LabelApplication（Label列印申请表）
  - packing_list（OneToOne PackingList）
  - applicant（FK User，填写人）
  - is_new_model（BooleanField，是否新机种变更）
  - form_data（JSONField，表单数据）
  - created_at（DateTimeField）

- ApprovalFlow（流程实例）
  - packing_list（OneToOne PackingList）
  - current_node（CharField，当前节点）
  - status（CharField，choices：pending/processing/closing/completed/rejected）
  - created_at、updated_at

- ApprovalNode（流程节点）
  - flow（FK ApprovalFlow）
  - stage（CharField，choices：label_apply/eng/qc/ie/label_close）
  - handler（FK User，指定的处理人）
  - actual_handler（FK User，实际处理人，用于代处理场景）
  - status（CharField，choices：pending/approved/rejected）
  - comment（TextField，审批意见/驳回理由）
  - reject_to（CharField，驳回目标部门，可选）
  - approved_at（DateTimeField）
  - created_at（DateTimeField）

## 后端接口清单

### 认证
- POST /api/auth/login/ — JWT 登录
- GET /api/auth/user/ — 当前用户信息（含部门、角色、主管）

### 装箱单
- POST /api/packing-list/ — 上传装箱单，创建流程实例
- GET /api/packing-list/ — 列表（按当前用户部门过滤）
- GET /api/packing-list/{id}/ — 详情

### Label申请表
- POST /api/label-application/ — 提交申请表（指定下一环节处理人、勾选新机种变更）

### 审批
- GET /api/approval/pending/ — 当前用户待审批列表
  - 普通职员：只看到指定给自己的
  - 主管：可看到本部门所有待办（加参数 ?scope=department）
- POST /api/approval/{node_id}/approve/ — 审批通过（指定下一环节处理人）
  - 支持代处理参数：on_behalf_of（被代理人 ID）
- POST /api/approval/{node_id}/reject/ — 驳回（选择打回部门 + 理由）
- GET /api/approval/flow/{flow_id}/ — 流程详情（含所有节点记录）

### 用户与部门
- GET /api/departments/ — 部门列表
- GET /api/users/?department=xxx — 按部门查用户
- GET /api/users/?department=xxx&role=supervisor — 按部门查主管
- GET /api/users/?supervisor=xxx — 查某主管下的职员

## 前端页面

### 公共
- 登录页
- 主布局（侧边栏 + 顶部栏 + 内容区）
- 顶部栏含语言切换按钮（EN / 中文）
- 路由守卫（未登录跳登录页）

### 业务页面
- 装箱单上传页（业务端用）
- 装箱单列表页（按状态筛选）
- Label申请表填写页（Label室用）
  - 显示装箱单信息
  - 勾选“是否新机种变更”（New Machine Type）
  - 根据勾选结果，显示对应部门的处理人选择器
- 待审批列表页（品管/IE/工程共用）
  - 主管多一个“本部门所有待办”标签页
- 审批详情页
  - 显示单据信息
  - 审批通过按钮（弹窗指定下一环节处理人）
  - 驳回按钮（弹窗选择打回部门 + 填理由）
  - 主管可勾选“代下属处理”，选择被代理人
- Label收尾页（Label室收尾用）
- 流程列表页（按状态筛选，按部门过滤）

### 管理员页面
- 用户管理（创建用户、分配部门、设置角色、设置主管）
- 部门管理

## 权限规则
- 业务端：只能上传装箱单、查看自己发起的流程
- Label室：只能处理分派到自己的 Label 申请表和收尾任务
- 品管/IE/工程：只能看到指定给自己的审批节点
- 主管：
  - 可查看本部门所有待办
  - 可代下属处理审批（记录实际处理人和被代理人）
- 管理员：管理用户和部门，可查看所有流程

## 交付要求
1. 按顺序输出代码：models.py → serializers.py → views.py → urls.py → 前端
2. 每个文件标注完整文件路径
3. 代码注释用中文，关键业务逻辑要说明清楚
4. 前后端接口字段保持一致
5. 前端用 Element Plus 组件，样式简洁即可
6. i18n 语言包覆盖所有界面文字，不能有硬编码中文
7. 部门名、状态名、角色名都要有中英双语

请从后端 accounts/models.py 开始。





# 下面是记录的一些创建细节：
# runserver 这个窗口不要关，它要一直开着服务。所有新命令都另开一个终端执行，新终端每次都要先 cd 到 backend 目录、再激活 .venv。

# 第1步：建总目录（在你想要的盘符下，比如 D 盘,已经创建过便不用）
mkdir D:\projects\label_automation
cd D:\projects\传签系统       

# 第2步：建后端目录
mkdir backend
cd backend                      # 现在你在：传签系统\backend\

# 第3步：创建虚拟环境（注意最后有个点）（换电脑需要）
python -m venv .venv

# 第4步：激活虚拟环境（换电脑需要）
.venv\Scripts\activate          # 激活后命令行前面出现 (.venv)
pip install django
# 第5步：装依赖(换电脑需要)
python -m pip install django djangorestframework djangorestframework-simplejwt django-cors-headers
pip install django djangorestframework djangorestframework-simplejwt django-cors-headers
python -m pip show django装完验证

# 第6步：创建 Django 项目（注意最后有个点）
django-admin startproject config .

# 第7步：启动验证
python manage.py runserver

accounts   ← 用户与部门
workflow   ← 传签流程核心
config     ← Django 配置
manage.py
db.sqlite3 ← 数据库
.venv      ← 虚拟环境 -->

# 临时切换node.js（当前终端生效）$env:PATH = "D:\LJX\node-v24;" + $env:PATH
$env:PATH = "E:\program\node-v24.21.0-win-x64\node-v24.21.0-win-x64;$env:PATH"
# 前端重新换电脑后

cd 你的项目路径\label_automation\frontend
npm install
npm.cmd -v
npm run dev

npm.cmd -v
npm.cmd install
npm.cmd run dev


Agent 改了 models.py 后，必须两步都做：

powershell
python manage.py makemigrations   # 生成迁移文件
python manage.py migrate          # 执行到数据库