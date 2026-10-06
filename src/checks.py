"""Integrity checks that print PASS/FAIL (Deliverable A7)."""


def check(name: str, condition: bool) -> bool:
    print(f"[{'PASS' if condition else 'FAIL'}] {name}")
    return condition
