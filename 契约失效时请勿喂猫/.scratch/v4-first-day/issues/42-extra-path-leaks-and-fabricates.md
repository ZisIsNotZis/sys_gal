# 42 — extra 通道四处破损：原始 JSON+inner 当台词、虚构道具、未发生的动作、没有自己的名字

Status: ready-for-agent
Need-review: yes
Need-test-cases: yes

## 复现与证据（同一工件）

1. **私有 JSON 当台词播报**（最严重）：世界事件 #1271/#1272（12:42，韩大叔=extra）
   `speech` 文本就是模型原始信封：
   `{"inner":"唐小岚把草稿的事交代给我了，三点前守好吧台就行…","name":"speak","arguments":{"text":"好嘞，那份草稿我不收不动…"}}`
   `heard=['唐小岚']`。**extra 的内心独白 + 协议结构被当成语音播给了对方**，唐小岚上下文里
   出现整段 JSON。全run 3 条同类事件（#1271/#1272/#1275）。
2. **虚构道具并坐实核心谜面**：图书馆 rare extra"校史研究社社长"（陈大爷，5 回合）断言
   "末页有抄写人签名，落款 2013 年 12 月 8 日""呼入…三通；抽水泵借出，写的是 23:30"。
   而 `manifest.yml` 无"抄件"实体，图书馆契约明写"抄件传闻就锁在那附近，但没人真的见过"。
   林瑶 turn 189 附和"学生证和借阅凭证您已经验过了"、turn 202 已把"先看末页抄写人签名和
   落款年月"写进行动计划——**一件不存在的证据进入了主角的调查链**。
3. **未发生的动作被叙述成已发生**：同 extra "好，开柜了""柜开了…你接稳了"；世界无任何
   open/take/give 事件，该 extra 五回合 affordances 全为 `[]`（只能 speak）。
4. **extra 不知道自己的名字**：`build_extra_system_prompt(fragment, notes, location)`
   （`npc_agent.py:203`）不注入本名，于是它自称第三人称"韩大叔"，还把自己的名字放进
   `to` 触发 `unknown or ambiguous speak recipient`。
5. **委托被静默回收**：12:27 唐小岚把"三点方老师来取草稿"郑重交给刚进门的兼职店员，
   12:53 `extra_removed 韩大叔 reason=idle` —— 她只看到"韩大叔 走了"，托付蒸发。

## 根因

extra 走的是另一条生成路径（`SPEAK_TOOLS` 只含 speak、affordances 为空），它既不共享
主 actor 的输出解析与校验，也不受"不得断言未建模物件"的世界契约约束；提示词只给了
场景片段与 knowledge_notes，没有任何名字/能力/边界声明。

## 验收方向

1. **输出解析统一**：extra 的返回必须与主 actor 走同一套信封解析（剥离 `inner` 与嵌套
   tool-call 结构），speak 文本里出现协议 JSON 形状即拒绝并要求重说。
2. **断言边界**：extra 的提示词与校验都要求"只可断言 knowledge_notes 与已注册实体范围内
   的具名物件/内容"；传闻物（如抄件）必须按 issue 35 的 `completeness: belief/missing`
   建模，只说传闻、不给细节。
3. **能力边界**：只能 speak 的角色不得把物理动作叙述成已发生（开柜/递件）；如剧情需要，
   就给 extra 真实 affordance 并产生世界事件。
4. **自名注入**：extra 提示词带上自己的名字与身份，避免第三人称自称与 `to` 自我投递。
5. **回收语义**：种子别把长期托付交给会话级 extra；或让 extra 离开时留下可被察觉的中断
   （现在只剩一句"走了"）。
6. 回归（先红后绿）：喂一段含 `inner` 的信封给 extra 路径 → 断言 speak 文本已剥离；
   断言 extra 断言未注册物件时被拒；断言 extra 离开产生可见的中断事件。
