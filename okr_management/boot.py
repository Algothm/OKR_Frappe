from __future__ import annotations


def boot_session(bootinfo):
    """Keep OKR Desk routes direct instead of nesting them under Check-In."""
    if getattr(bootinfo, "module_wise_workspaces", None) is not None:
        bootinfo.module_wise_workspaces["OKR Management"] = []
