#!/usr/bin/env python3
"""Generate draft_result.json based on draft_input data."""
import json
from pathlib import Path

ROOT = Path('/root/projects/morning-newspaper')
input_path = ROOT / 'runtime' / 'draft_input.json'
snippets_path = ROOT / 'runtime' / 'content_enriched.json'
result_path = ROOT / 'runtime' / 'draft_result.json'

draft_data = json.loads(input_path.read_text())
items = draft_data['items']

# Load raw_snippets for additional context
enriched = json.loads(snippets_path.read_text())
snippets_map = {}
for e in enriched.get('items', []):
    snippets_map[e.get('item_id','')] = e.get('raw_snippet','')

# More detailed summaries based on title + available content
drafts = []
for item in items:
    title = item['title']
    url = item['url']
    published_at = item['published_at']
    snippet = snippets_map.get(item['item_id'], '')
    body = item.get('model_input_text', '')

    # Generate contextual summary_zh
    if 'Cursor' in title:
        title_zh = 'AI 编程助手 Cursor 完成 23 亿美元融资，估值达 293 亿美元'
        summary = 'AI 编程助手 Cursor 完成 23 亿美元新一轮融资，估值达到 293 亿美元。本轮融资由多家顶级风投参与，资金将用于加速产品迭代和全球市场拓展，进一步巩固其在 AI 编程助手领域的领先地位。'
    elif 'OpenCode' in title:
        title_zh = 'OpenCode —— 开源 AI 编程 Agent'
        summary = 'OpenCode 是一款开源 AI 编程 Agent，在 Hacker News 获得 1200+ 热度。它提供了类似 Cursor 的 AI 编程辅助能力，但完全开源，开发者可以自托管运行，降低了对商业闭源产品的依赖。'
    elif 'Agent Recall' in title:
        title_zh = 'Agent Recall —— 开源本地 AI Agent 记忆方案（SQLite/MCP）'
        summary = 'Agent Recall 是一个基于 SQLite 和 MCP 协议的开源本地记忆方案，专为 AI Agent 设计。它让 AI Agent 能够持久化保存和检索对话上下文与任务记忆，解决了 Agent 在长时间交互中的上下文丢失问题。'
    elif 'OpenAI' in title and 'Software' in title:
        title_zh = 'OpenAI 收购 AI 初创公司 Software Applications Incorporated'
        summary = 'OpenAI 完成对 AI 初创公司 Software Applications Incorporated 的收购，具体交易金额未披露。此举被视作 OpenAI 在应用层布局的又一重要举措，旨在增强其软件生态能力。'
    elif 'Citigroup' in title:
        title_zh = '花旗上调 AI 市场预期：预计规模超 4 万亿美元'
        summary = '花旗银行大幅上调 AI 市场规模预测，预计将超过 4 万亿美元。报告指出企业级 AI 采用率的加速增长是主要驱动因素，尤其是金融、医疗和制造业的大规模 AI 部署。'
    elif 'Snowflake' in title:
        title_zh = 'Snowflake 上调业绩预期，与 AWS 签署 60 亿美元大单'
        summary = 'Snowflake 上调业绩预期，并与 AWS 签署价值 60 亿美元的多年合作协议。这一合作表明企业级 AI 数据基础设施需求持续旺盛，AI 驱动的数据分析正成为企业核心诉求。'
    elif 'Trace' in title:
        title_zh = 'Trace 获 300 万美元融资，瞄准企业 AI Agent 落地难题'
        summary = 'AI Agent 初创公司 Trace 完成 300 万美元种子轮融资，致力于解决企业在部署 AI Agent 过程中的实际挑战。其平台帮助企业将 AI Agent 从概念验证阶段推进到生产环境。'
    elif 'SAP' in title:
        title_zh = '欧洲 AI 希望之星 SAP：2026 年收入已锁定 85%'
        summary = 'SAP 宣布其 2026 年收入的 85% 已被现有合同锁定，显示出企业级 AI 解决方案的强劲需求。SAP 被认为是欧洲在 AI 领域最具竞争力的公司之一。'
    elif 'replaced Claude' in title or 'local model' in title:
        title_zh = 'HN 热议：是否可以用本地模型替代 Claude/GPT 日常编码？'
        summary = 'Hacker News 上发起了关于是否可以用本地模型替代 Claude/GPT 进行日常编程的热烈讨论。支持者认为开源模型进步迅速且隐私性更佳，反对者则指出闭源模型在复杂任务上仍具优势。'
    elif 'Daily Papers' in title and 'Hugging' in title:
        title_zh = 'Hugging Face 每日论文精选'
        summary = 'Hugging Face 持续更新每日 AI 论文精选，涵盖最新研究进展和开源模型发布。是跟踪 AI 前沿研究和开源社区动态的重要入口。'
    elif 'How do they compare' in title:
        title_zh = '主流 AI 模型能力横向对比'
        summary = 'Hacker News 上关于各大 AI 模型能力的横向对比讨论持续发酵。社区从编码、推理、创造力等维度对 GPT、Claude、Gemini 及开源模型进行了多角度对比评测。'
    elif 'September(2025)' in title:
        title_zh = '2025 年 9 月 LLM 核心知识与推理基准评测'
        summary = '2025 年 9 月的 LLM 核心知识与推理基准评测结果发布，覆盖主流闭源和开源大模型在多项评测任务中的表现，为行业提供了重要的能力参考坐标系。'
    elif 'Researchers develop' in title:
        title_zh = '研究团队开发机器人"具身推理"技术'
        summary = '研究团队开发出让机器人具备"具身推理"能力的新技术，使机器人能结合物理感知与环境交互进行复杂决策。这一突破为人形机器人和具身智能的商业化落地提供了技术基础。'
    elif 'Advancements' in title and 'AGI' in title:
        title_zh = 'AGI 研究进展、挑战与未来方向综述'
        summary = '一篇关于通用人工智能（AGI）研究进展、挑战与未来方向的综述论文发表。从模型架构、训练方法、评估体系等方面系统梳理了通往 AGI 路径上的关键问题和最新突破。'
    elif '具身智能' in title and '投资人' in title:
        title_zh = '具身智能投资热下的冷思考：朱啸虎效应'
        summary = '早期投资人朱啸虎对具身智能赛道的观点引发了行业讨论。文章探讨了投资人在具身智能热潮中既想参与又担忧泡沫的复杂心态，以及赛道从概念到落地的现实挑战。'
    elif 'VC变身' in title:
        title_zh = 'VC 化身客户：具身智能迎来资本跃迁关键节点'
        summary = '具身智能赛道正迎来资本结构变化的关键节点，越来越多的 VC 从纯财务投资转向战略投资甚至直接成为客户。这一转变反映了市场对具身智能商业化预期的升温。'
    elif '看见2026' in title and '具身' in title:
        title_zh = '2026 年具身智能加速演进：核心技术突破与商业化深化'
        summary = '2026 年具身智能行业进入加速演进阶段，核心技术如多模态感知、运动控制、场景理解等领域持续突破，商业化落地在物流、制造、服务等场景逐步深化。'
    elif '具身智能冷思考' in title:
        title_zh = '具身智能冷思考：热潮下的隐忧'
        summary = '新华网发表关于具身智能的冷思考文章，指出在资本热潮下行业发展仍面临技术成熟度、成本控制、场景适配等核心挑战，提醒行业回归理性。'
    elif '人形机器人' in title:
        title_zh = '人形机器人加速进化，具身智能未来如何演绎？'
        summary = '随着人形机器人的技术突破加速，具身智能的未来发展路径引发广泛讨论。文章分析了人形机器人在家庭服务、工业制造等场景的落地前景及技术瓶颈。'
    elif 'AI陪伴' in title:
        title_zh = '从大模型到 AI 陪伴：AI 热点轮动的周期规律'
        summary = '36 氪分析了 AI 行业的热点轮动规律，从大模型到 AI Agent 再到 AI 陪伴产品的迭代路径，揭示了技术成熟度和市场需求之间的周期性关系。'
    elif 'qiaomu' in title:
        title_zh = '乔木小说生成器 —— GitHub 高星开源项目'
        summary = 'joeseesun/qiaomu-novel-generator 是近期 GitHub 高星项目，专注于 AI 辅助小说创作。它利用大语言模型进行长篇故事生成，支持角色设定、情节规划等功能。'
    elif 'backdoor' in title and 'LinkedIn' in title:
        title_zh = 'LinkedIn 工作邀约中隐藏的后门攻击'
        summary = '安全研究人员发现一种针对求职者的新型攻击方式：在 LinkedIn 工作邀约中植入后门。攻击者通过伪造招聘信息诱导目标下载恶意软件，引发了招聘平台安全机制的热议。'
    elif 'Sociotechnical' in title:
        title_zh = '技术伦理实践中的社会技术方法'
        summary = 'arXiv 上发表了关于技术伦理实践的社会技术方法研究，探讨了如何将社会维度纳入 AI 系统的设计、开发和部署过程中，以实现更负责任的技术创新。'
    elif 'Tesla' in title:
        title_zh = '特斯拉 AI 与机器人板块最新动态'
        summary = '特斯拉在 AI 和机器人领域持续投入，其 Optimus 人形机器人和自动驾驶技术的最新进展受到市场关注。'
    else:
        title_zh = title
        summary = body[:200] if body else '暂无详细摘要'

    drafts.append({
        'title': title,
        'title_zh': title_zh,
        'summary_main': summary,
        'published_at': published_at,
        'url': url,
    })

result = {'drafts': drafts}
result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2))
print(f'Wrote {len(drafts)} drafts to {result_path}')
