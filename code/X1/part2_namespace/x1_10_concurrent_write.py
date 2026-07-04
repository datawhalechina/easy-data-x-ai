"""
x1_10_concurrent_write.py — 并发写入冲突与缓解策略

两个 Agent 同时更新同一条用户画像字段, 会发生什么?

三种策略对比:
  1. no_lock:           直接覆盖, 后写入静默覆盖先写入 → 数据丢失
  2. lww_timestamp:     最后写入胜出, 依赖时钟同步, NTP 误差可能导致意外行为
  3. optimistic_lock:   乐观锁(version 字段), 写入时 CAS 检查, 冲突自动重试

运行:
  python x1_10_concurrent_write.py

输出: 每种策略下两个 Agent 的写入结果和最终状态

推荐: 乐观锁是最小成本的工程方案
  - 不同 Agent 更新不同字段 → 各自独立, 无冲突
  - 同一字段需要仲裁 → version + CAS + 最多 3 次重试

对应正文: X1-2 §3.3 "乐观锁：共享画像的最小仲裁"
"""

import json
import os
import threading
import time
from datetime import datetime
from typing import Any


def simulate_concurrent_write(strategy: str = "no_lock") -> dict:
    """
    模拟两个线程（Agent）并发写入同一 key。

    策略：
    - no_lock: 无保护，后写入覆盖先写入（可能丢数据）
    - optimistic_lock: 乐观锁（version 检查），冲突时重试
    - lww_timestamp: 最后写入胜出（基于时间戳）
    """

    # 共享状态
    shared_profile: dict[str, Any] = {
        "preferred_language": "Java",
        "version": 1,
        "updated_at": "",  # 空字符串作为哨兵值，避免 LWW 首次比较时 str > None 报错
        "updated_by": None,
    }
    write_log: list[dict] = []
    lock = threading.Lock()

    def agent_a_write():
        """Agent A：用户已从 Java 转向 Go"""
        time.sleep(0.01)  # 模拟网络延迟

        if strategy == "no_lock":
            # 直接覆盖，不管当前状态
            shared_profile["preferred_language"] = "Go"
            shared_profile["updated_by"] = "agent_code_assistant"
            shared_profile["updated_at"] = datetime.now().isoformat()
            write_log.append({"agent": "A (代码助手)", "content": "Go", "result": "written"})

        elif strategy == "optimistic_lock":
            # 乐观锁：读在锁外，写在锁内，模拟真实的读-改-写窗口
            for attempt in range(3):
                # 锁外读：记录读取时的 version
                current_version = shared_profile["version"]
                # 模拟读后处理（此时其他线程可能已修改 version）
                time.sleep(0.05)
                with lock:
                    # CAS 检查：version 是否仍是读取时的值
                    if shared_profile["version"] == current_version:
                        shared_profile["preferred_language"] = "Go"
                        shared_profile["version"] += 1
                        shared_profile["updated_by"] = "agent_code_assistant"
                        shared_profile["updated_at"] = datetime.now().isoformat()
                        write_log.append({
                            "agent": "A (代码助手)",
                            "content": "Go",
                            "result": f"written (v{shared_profile['version']}, attempts={attempt+1})",
                        })
                        break
                    # version 已变 → 冲突，重试
            else:
                write_log.append({
                    "agent": "A (代码助手)",
                    "content": "Go",
                    "result": "conflict_retry_failed (3 次重试均失败)",
                })

        elif strategy == "lww_timestamp":
            ts = datetime.now().isoformat()
            time.sleep(0.005)  # 确保时间戳有先后
            with lock:
                existing_ts = shared_profile.get("updated_at", "")
                if ts > existing_ts:
                    shared_profile["preferred_language"] = "Go"
                    shared_profile["updated_by"] = "agent_code_assistant"
                    shared_profile["updated_at"] = ts
                    write_log.append({"agent": "A", "content": "Go", "result": "written (newer)"})
                else:
                    write_log.append({"agent": "A", "content": "Go", "result": "rejected (older)"})

    def agent_b_write():
        """Agent B：用户现在用 Rust 做主力"""
        if strategy == "no_lock":
            shared_profile["preferred_language"] = "Rust"
            shared_profile["updated_by"] = "agent_project_manager"
            shared_profile["updated_at"] = datetime.now().isoformat()
            write_log.append({"agent": "B (PM助手)", "content": "Rust", "result": "written"})

        elif strategy == "optimistic_lock":
            for attempt in range(3):
                current_version = shared_profile["version"]
                time.sleep(0.05)
                with lock:
                    if shared_profile["version"] == current_version:
                        shared_profile["preferred_language"] = "Rust"
                        shared_profile["version"] += 1
                        shared_profile["updated_by"] = "agent_project_manager"
                        shared_profile["updated_at"] = datetime.now().isoformat()
                        write_log.append({
                            "agent": "B (PM助手)",
                            "content": "Rust",
                            "result": f"written (v{shared_profile['version']}, attempts={attempt+1})",
                        })
                        break
            else:
                write_log.append({
                    "agent": "B (PM助手)",
                    "content": "Rust",
                    "result": "conflict_retry_failed (3 次重试均失败)",
                })

        elif strategy == "lww_timestamp":
            ts = datetime.now().isoformat()
            with lock:
                existing_ts = shared_profile.get("updated_at", "")
                if ts > existing_ts:
                    shared_profile["preferred_language"] = "Rust"
                    shared_profile["updated_by"] = "agent_project_manager"
                    shared_profile["updated_at"] = ts
                    write_log.append({"agent": "B", "content": "Rust", "result": "written (newer)"})
                else:
                    write_log.append({"agent": "B", "content": "Rust", "result": "rejected (older)"})

    # 启动并发线程
    t1 = threading.Thread(target=agent_a_write)
    t2 = threading.Thread(target=agent_b_write)
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    return {
        "final_state": dict(shared_profile),
        "write_log": write_log,
    }


def main():
    print("=" * 85)
    print("X1-10 并发写入冲突演示")
    print("场景：Agent A（代码助手）和 Agent B（PM 助手）同时更新「用户编程语言偏好」")
    print(f"{'=' * 85}")

    strategies = [
        ("no_lock", "无保护（直接覆盖）"),
        ("lww_timestamp", "最后写入胜出（LWW）"),
        ("optimistic_lock", "乐观锁（version 检查）"),
    ]

    for strategy, label in strategies:
        print(f"\n{'-' * 85}")
        print(f"策略: {label}")
        print(f"{'-' * 85}")

        result = simulate_concurrent_write(strategy)

        for entry in result["write_log"]:
            print(f"  {entry['agent']}: 写入 '{entry['content']}' → {entry['result']}")

        final = result["final_state"]
        print(f"\n  最终状态：preferred_language = '{final['preferred_language']}'")
        print(f"  更新者：{final['updated_by']}")

        if strategy == "no_lock":
            if final["preferred_language"] in ("Go", "Rust"):
                print(f"  [!] 问题：两个写入中丢失了一个！用户偏好是 '{final['preferred_language']}'，"
                      f"但另一个 Agent 的写入被无声覆盖。")
                print(f"    更糟的是——我们不知道哪个是'正确的'，后到的覆盖了先到的。")

        elif strategy == "lww_timestamp":
            print(f"  注意：LWW 保证了确定性（时间戳更大的胜出），但不保证正确性。")
            print(f"  如果 Agent A 的更新更准确但时钟慢了 1ms，正确数据就丢了。")

        elif strategy == "optimistic_lock":
            # 检查两条是否都写入成功
            both_written = all("written" in e["result"] for e in result["write_log"])
            # attempts > 1 才算真正经历过 CAS 冲突重试
            import re as _re
            retry_count = sum(
                1 for e in result["write_log"]
                if "attempts=" in e["result"] and int(_re.search(r"attempts=(\d+)", e["result"]).group(1)) > 1
            )
            if both_written:
                print(f"  [v] 乐观锁 + CAS 重试：两个写入最终都成功")
                if retry_count > 0:
                    print(f"    其中 {retry_count} 个写入经历了「读到旧版本 → CAS 失败 → 重试」过程")
                print(f"    version 从 1 → {final['version']}，每次自增对应一次成功的 CAS")
            else:
                print(f"  [!] 重试失败，一个写入被拒绝（需要业务层处理）")

    # 结论
    print(f"\n{'=' * 85}")
    print("总结与建议")
    print(f"{'=' * 85}")
    print(f"  1. 无保护写入在多 Agent 场景下不可接受——数据会静默丢失。")
    print(f"  2. LWW 实现简单但依赖时钟同步，NTP 误差可能导致意外行为。")
    print(f"  3. 乐观锁（version）是最小成本的工程方案：")
    print(f"     - 写入时携带当前 version，服务端检查 CAS")
    print(f"     - 冲突时自动重试（最多 3 次）")
    print(f"     - version chain 提供完整的变更历史")
    print(f"  4. 对于用户画像类字段（结构化、单值），建议：")
    print(f"     - 不同 Agent 更新不同字段 → 各自独立，无冲突")
    print(f"     - 同一字段需要仲裁 → 乐观锁 + 冲突时通知用户")
    print()


if __name__ == "__main__":
    main()
