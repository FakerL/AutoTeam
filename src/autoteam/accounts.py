"""账号池管理 - 持久化存储所有账号状态"""

import json
import time
from pathlib import Path

from autoteam.admin_state import get_admin_email
from autoteam.textio import read_text, write_text

PROJECT_ROOT = Path(__file__).parent.parent.parent
ACCOUNTS_FILE = PROJECT_ROOT / "accounts.json"
ROTATION_STATE_FILE = PROJECT_ROOT / "rotation_state.json"

# 账号状态
STATUS_ACTIVE = "active"  # 在 team 中，额度可用
STATUS_EXHAUSTED = "exhausted"  # 在 team 中，额度用完
STATUS_STANDBY = "standby"  # 已移出 team，等待额度恢复
STATUS_PENDING = "pending"  # 已邀请，等待注册完成


def _normalized_email(value):
    return (value or "").strip().lower()


def _is_main_account_email(email):
    return bool(_normalized_email(email)) and _normalized_email(email) == _normalized_email(get_admin_email())


def quota_snapshot_display_status(quota_info, *, now=None):
    """根据额度快照推导展示状态；已过重置时间的历史耗尽快照不再显示为 exhausted。"""
    if not isinstance(quota_info, dict):
        return ""

    from autoteam.codex_auth import get_quota_exhausted_info, quota_result_resets_at

    exhausted_info = get_quota_exhausted_info(quota_info)
    if exhausted_info:
        current_ts = time.time() if now is None else now
        resets_at = quota_result_resets_at(exhausted_info)
        if not resets_at or current_ts < resets_at:
            return STATUS_EXHAUSTED

    has_quota_values = any(isinstance(quota_info.get(key), (int, float)) for key in ("primary_pct", "weekly_pct"))
    return STATUS_ACTIVE if has_quota_values else ""


def load_accounts():
    """加载账号列表"""
    if ACCOUNTS_FILE.exists():
        text = read_text(ACCOUNTS_FILE).strip()
        if text:
            return json.loads(text)
    return []


def save_accounts(accounts):
    """保存账号列表"""
    write_text(ACCOUNTS_FILE, json.dumps(accounts, indent=2, ensure_ascii=False))


def load_rotation_state():
    """加载轮转游标状态。"""
    if ROTATION_STATE_FILE.exists():
        try:
            text = read_text(ROTATION_STATE_FILE).strip()
            if text:
                data = json.loads(text)
                if isinstance(data, dict):
                    return data
        except Exception:
            return {}
    return {}


def save_rotation_state(state):
    """保存轮转游标状态。"""
    write_text(ROTATION_STATE_FILE, json.dumps(state, indent=2, ensure_ascii=False))


def get_next_reuse_email():
    """获取下次 standby 复用的起始邮箱。"""
    value = load_rotation_state().get("next_reuse_email")
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def set_next_reuse_email(email):
    """保存下次 standby 复用的起始邮箱。"""
    state = load_rotation_state()
    normalized = (email or "").strip()
    if normalized:
        state["next_reuse_email"] = normalized
    else:
        state.pop("next_reuse_email", None)
    save_rotation_state(state)
    return normalized or None


def advance_reuse_cursor(email):
    """在账号总顺序中，把复用游标推进到当前邮箱的下一个账号。"""
    ordered_accounts = [a for a in load_accounts() if not _is_main_account_email(a.get("email"))]
    if not ordered_accounts:
        return set_next_reuse_email(None)

    current_idx = next(
        (idx for idx, acc in enumerate(ordered_accounts) if _normalized_email(acc.get("email")) == _normalized_email(email)),
        None,
    )
    if current_idx is None:
        return get_next_reuse_email()

    next_email = ordered_accounts[(current_idx + 1) % len(ordered_accounts)].get("email")
    return set_next_reuse_email(next_email)


def find_account(accounts, email):
    """按邮箱查找账号"""
    for acc in accounts:
        if acc["email"] == email:
            return acc
    return None


def add_account(email, password, cloudmail_account_id=None):
    """添加新账号"""
    accounts = load_accounts()
    if find_account(accounts, email):
        return  # 已存在

    accounts.append(
        {
            "email": email,
            "password": password,
            "cloudmail_account_id": cloudmail_account_id,
            "status": STATUS_PENDING,
            "auth_file": None,  # CPA 认证文件路径
            "quota_exhausted_at": None,  # 额度用完的时间
            "quota_resets_at": None,  # 额度恢复时间
            "created_at": time.time(),
            "last_active_at": None,
        }
    )
    save_accounts(accounts)


def update_account(email, **kwargs):
    """更新账号字段"""
    accounts = load_accounts()
    acc = find_account(accounts, email)
    if acc:
        acc.update(kwargs)
        save_accounts(accounts)
    return acc


def get_active_accounts():
    """获取所有活跃账号"""
    return [a for a in load_accounts() if a["status"] == STATUS_ACTIVE and not _is_main_account_email(a.get("email"))]


def get_standby_accounts():
    """获取所有待命账号（已移出 team，可能额度已恢复）"""
    accounts = load_accounts()
    now = time.time()
    standby = []
    for a in accounts:
        if _is_main_account_email(a.get("email")):
            continue
        if a["status"] == STATUS_STANDBY:
            resets_at = a.get("quota_resets_at")
            if resets_at is None:
                # 没有恢复时间 = 不是因为额度用完被移出的，随时可复用
                a["_quota_recovered"] = True
            else:
                # 有恢复时间，看是否已过
                a["_quota_recovered"] = now >= resets_at
            standby.append(a)

    next_reuse_email = get_next_reuse_email()
    if standby and next_reuse_email:
        order_map = {
            _normalized_email(acc.get("email")): idx
            for idx, acc in enumerate(accounts)
            if not _is_main_account_email(acc.get("email"))
        }
        start_idx = order_map.get(_normalized_email(next_reuse_email))
        if start_idx is not None and order_map:
            standby.sort(
                key=lambda acc: (
                    order_map.get(_normalized_email(acc.get("email")), len(order_map)) - start_idx
                )
                % len(order_map)
            )

    recovered = [acc for acc in standby if acc.get("_quota_recovered", False)]
    unrecovered = [acc for acc in standby if not acc.get("_quota_recovered", False)]
    return recovered + unrecovered


def get_next_reusable_account():
    """获取下一个可重用的 standby 账号（优先额度已恢复的）"""
    standby = get_standby_accounts()
    if standby:
        return standby[0]
    return None
