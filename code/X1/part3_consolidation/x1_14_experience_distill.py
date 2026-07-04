"""
x1_14_experience_distill.py — 情景记忆 → 经验三元组 → Skill 雏形

本脚本演示 X1 系列与 P4/X2 的核心衔接点: 记忆系统的输出如何成为 Skill 系统的输入。

三步流程:
  1. 提取: 从情景记忆中结构化提取 (问题, 方案, 结果) 三元组
  2. 聚类: 同类成功经验聚合 → 归纳为可复用的经验模式
  3. 外化: 经验模式 → Skill 描述 → 可注入 System Prompt 的行为规则

运行:
  python x1_14_experience_distill.py

输入: 8 条内置情景记忆 (覆盖数据处理、Web 框架、部署运维、学习路径)
输出:
  - 每条情景记忆的结构化三元组
  - 按领域聚类的经验模式及置信度
  - 高置信度模式 → Skill 描述

闭环意义:
  记忆系统"记住偏好" → 蒸馏为经验 → 外化为 Skill
  Agent 从被动记住进化到主动适应

对应正文: X1-3 §4 "从经验到 Skill"
"""

import json
from typing import Any
from collections import defaultdict


def extract_experience_triples(episodic_memories: list) -> list:
    """
    从情景记忆中提取经验三元组：(问题情境, 采取方案, 结果)

    实际系统中由 LLM 完成：
    "从以下交互记录中提取 (问题, 方案, 结果) 三元组"
    """
    triples = []
    for mem in episodic_memories:
        triple = {
            "source_id": mem["id"],
            "problem": mem.get("problem", ""),
            "solution": mem.get("solution", ""),
            "result": mem.get("result", ""),
            "success": "成功" in mem.get("result", "") or "效果好" in mem.get("result", ""),
            "domain": mem.get("domain", "通用"),
        }
        triples.append(triple)
    return triples


def cluster_experiences(triples: list) -> dict:
    """按领域聚类经验，归纳为经验模式"""
    by_domain = defaultdict(list)
    for t in triples:
        if t["success"]:
            by_domain[t["domain"]].append(t)

    patterns = {}
    for domain, exp_list in by_domain.items():
        if len(exp_list) >= 2:  # 至少两条同类经验才能形成模式
            # 模拟 LLM 归纳
            pattern = _induce_pattern(domain, exp_list)
            patterns[domain] = pattern

    return patterns


def _induce_pattern(domain: str, experiences: list) -> dict:
    """模拟 LLM 从同类经验中归纳模式"""
    templates = {
        "数据处理": {
            "pattern": "处理大数据文件时，优先推荐 Python/pandas 生态的 chunked reading 方案，避免加载全量到内存",
            "confidence": 0.82,
            "support_count": len(experiences),
        },
        "Web 框架选型": {
            "pattern": "做 Web 项目时推荐 Django（用户熟悉），新项目可考虑 FastAPI（性能更好）",
            "confidence": 0.78,
            "support_count": len(experiences),
        },
        "部署运维": {
            "pattern": "部署方案优先考虑容器化（Docker），编排层按项目规模从 docker-compose 到 K8s 递增",
            "confidence": 0.75,
            "support_count": len(experiences),
        },
        "学习路径": {
            "pattern": "学习新技术时建议动手实践优先，先搭建最小可用原型再深入理论",
            "confidence": 0.88,
            "support_count": len(experiences),
        },
    }

    result = templates.get(domain, {
        "pattern": f"在 {domain} 领域，用户偏好方案待进一步积累经验",
        "confidence": 0.5,
        "support_count": len(experiences),
    })
    result["domain"] = domain
    result["source_experiences"] = [e["source_id"] for e in experiences]
    return result


def to_skill_description(pattern: dict) -> str:
    """
    将经验模式转化为 Skill 描述。
    这是记忆系统输出 → Skill 系统输入的关键衔接点。
    """
    return (
        f"## Skill: {pattern['domain']} 处理经验\n\n"
        f"**触发条件**: 当用户提出 {pattern['domain']} 相关的问题时\n\n"
        f"**行为规则**: {pattern['pattern']}\n\n"
        f"**置信度**: {pattern['confidence']:.0%}\n"
        f"**支撑经验**: {pattern['support_count']} 条\n\n"
        f"*此 Skill 由记忆系统从用户过往交互中自动蒸馏生成，非人工编写。*"
    )


def main():
    # 模拟情景记忆
    episodic_memories = [
        {
            "id": "ep001",
            "problem": "用户需要从 500 万行 CSV 中提取统计数据",
            "solution": "推荐了 pandas + chunksize 分批读取方案",
            "result": "方案成功，处理时间从预估的 30 分钟降到 2 分钟",
            "domain": "数据处理",
        },
        {
            "id": "ep002",
            "problem": "用户需要导入 100 万行日志数据进行分析",
            "solution": "推荐了 Python + seekdb 方案，用 parquet 格式存储中间结果",
            "result": "方案成功，用户表示效果好",
            "domain": "数据处理",
        },
        {
            "id": "ep003",
            "problem": "用户需要搭建一个内部管理系统",
            "solution": "推荐了 Django Admin + 自定义模板方案",
            "result": "方案成功，一天内搭建完成",
            "domain": "Web 框架选型",
        },
        {
            "id": "ep004",
            "problem": "用户想为一个已有项目添加 REST API",
            "solution": "推荐了 Django REST Framework",
            "result": "方案成功，API 文档自动生成",
            "domain": "Web 框架选型",
        },
        {
            "id": "ep005",
            "problem": "用户想把新开发的服务部署到服务器",
            "solution": "推荐了 Docker + docker-compose 方案",
            "result": "方案成功，一次部署通过",
            "domain": "部署运维",
        },
        {
            "id": "ep006",
            "problem": "用户想学习 Rust 但不知道从哪里开始",
            "solution": "推荐先看 Rustlings 小练习，再搭一个简单 REST API 实践",
            "result": "方案成功，用户在一周内完成了 Rustlings 并搭建了第一个 API",
            "domain": "学习路径",
        },
        {
            "id": "ep007",
            "problem": "用户想系统学习 Kubernetes",
            "solution": "推荐了 minikube 本地环境 + 官方 interactive tutorial",
            "result": "方案成功，用户按建议搭建了本地环境",
            "domain": "学习路径",
        },
        {
            "id": "ep008",
            "problem": "用户需要快速开发一个数据看板",
            "solution": "推荐了 Streamlit + plotly 方案",
            "result": "方案成功，半天内完成看板原型",
            "domain": "数据处理",
        },
    ]

    print("=" * 85)
    print("X1-14 经验蒸馏：情景记忆 → 经验三元组 → Skill 雏形")
    print(f"{'=' * 85}")

    # 步骤 1：提取经验三元组
    print(f"\n步骤 1：从 {len(episodic_memories)} 条情景记忆中提取经验三元组")
    triples = extract_experience_triples(episodic_memories)
    for t in triples:
        status = "[v] 成功" if t["success"] else "[x] 失败"
        print(f"  [{t['source_id']}] ({t['domain']}) {status}")
        print(f"    问题: {t['problem'][:50]}...")
        print(f"    方案: {t['solution'][:50]}...")

    # 步骤 2：聚类归纳
    print(f"\n步骤 2：按领域聚类，归纳经验模式")
    patterns = cluster_experiences(triples)
    for domain, pattern in patterns.items():
        print(f"\n  * [{domain}] (置信度={pattern['confidence']:.2f}, "
              f"支撑经验={pattern['support_count']} 条)")
        print(f"    模式: {pattern['pattern']}")
        print(f"    来源: {', '.join(pattern['source_experiences'])}")

    # 步骤 3：转化为 Skill 描述
    print(f"\n{'-' * 85}")
    print("步骤 3：经验模式 → Skill 描述")
    print(f"{'-' * 85}")

    for domain, pattern in patterns.items():
        if pattern["confidence"] >= 0.8:
            skill_desc = to_skill_description(pattern)
            print(f"\n{skill_desc}")

    # 关键观察
    print(f"\n{'=' * 85}")
    print("关键观察：记忆系统 → Skill 系统的衔接")
    print(f"{'=' * 85}")
    print(f"  1. 情景记忆 → 经验三元组（问题, 方案, 结果）")
    print(f"     → 从原始交互中结构化为可分析的经验单元")
    print(f"  2. 经验三元组 → 经验模式")
    print(f"     → 同类经验聚类，归纳为可复用的行为规则（需 ≥ 2 条支撑）")
    print(f"  3. 经验模式 → Skill 描述")
    print(f"     → 经验外化到一定程度后，成为可注入 System Prompt 的 Skill 规则")
    print(f"  4. 闭环：记忆系统「记住偏好」→ 蒸馏成经验 → 外化为 Skill")
    print(f"     → Agent 从被动记住进化到主动适应")
    print()


if __name__ == "__main__":
    main()
