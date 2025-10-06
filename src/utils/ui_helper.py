"""
UI Helper utilities for formatting bot messages and responses.
"""
import os
import psutil
import platform
from datetime import datetime
from typing import Dict, Any, Optional

def format_bytes(bytes: int) -> str:
    """Format bytes into human readable format"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes < 1024:
            return f"{bytes:.1f}{unit}"
        bytes /= 1024
    return f"{bytes:.1f}TB"

def format_duration(seconds: float) -> str:
    """Format duration in seconds to human readable format"""
    if seconds < 60:
        return f"{seconds:.1f}s"
    minutes = seconds / 60
    if minutes < 60:
        return f"{minutes:.1f}m"
    hours = minutes / 60
    return f"{hours:.1f}h"

def get_system_metrics() -> Dict[str, Any]:
    """Get current system metrics"""
    process = psutil.Process()
    
    return {
        "open_fds": process.num_fds() if hasattr(process, 'num_fds') else 0,
        "cpu_time": sum(process.cpu_times()),
        "memory_virtual": process.memory_info().vms,
        "memory_used": process.memory_info().rss,
        "runtime": platform.python_implementation(),
        "version": platform.python_version(),
        "uptime": (datetime.now() - datetime.fromtimestamp(process.create_time())).total_seconds()
    }

def format_mission_status(metrics: Dict[str, Any], stats: Dict[str, Any]) -> str:
    """Format a comprehensive mission status report"""
    system = get_system_metrics()
    
    return f"""
🚀 MISSION STATUS REPORT
==============================
📅 Report Time: {datetime.now().strftime('%b %d, %Y at %I:%M %p')}

🔧 SYSTEM VITALS
------------------------------
├─ 📡 Open FDs    : {system['open_fds']}
├─ 🧠 CPU Usage   : {system['cpu_time']:.1f}s total
╰─ ⏱️ Uptime      : {format_duration(system['uptime'])}

💾 MEMORY STATUS
------------------------------
├─ 💽 Virtual Mem : {format_bytes(system['memory_virtual'])}
├─ 💾 Memory Used : {format_bytes(system['memory_used'])}

🎯 DOWNLOAD STATS
------------------------------
├─ 📥 Downloaded  : {stats.get('total_downloaded', 0)}
├─ 📤 Uploaded    : {stats.get('total_uploaded', 0)}
├─ ❌ Failed      : {stats.get('total_failed', 0)}
╰─ 💽 Total Size  : {format_bytes(stats.get('total_size', 0))}

⚙️ RUNTIME ENVIRONMENT
------------------------------
├─ 🐍 Runtime    : {system['runtime']} {system['version']}
╰─ ⚡ Status     : {'✅ Online' if metrics.get('healthy', True) else '⚠️ Warning'}

------------------------------
📊 Status Indicators
✅ Normal | ⚠️ Warning | ⛔️ Critical

This is an automated health report
"""

def format_job_progress(
    job_id: str, 
    downloaded: int,
    uploaded: int,
    failed: int,
    total: int,
    duration: Optional[float] = None,
    error: Optional[str] = None
) -> str:
    """Format job progress message"""
    status = "✅ completed" if uploaded + failed == total else "⏳ in progress"
    if error:
        status = "❌ failed"

    msg = f"""
📊 Job Status: {job_id}
══════════════════════

📥 Downloaded: {downloaded}/{total}
📤 Uploaded: {uploaded}/{total}
❌ Failed: {failed}
⏳ Pending: {total - (uploaded + failed)}

⚡ Status: {status}"""

    if duration:
        msg += f"\n⏱️ Duration: {format_duration(duration)}"

    if error:
        msg += f"\n\n❌ Error: {error}"
    elif uploaded + failed == total:
        msg += "\n\n🎉 All files processed!"

    return msg

def format_session_info(session: Dict[str, Any]) -> str:
    """Format session information message"""
    status = "✅ Active" if session.get('active', False) else "⚠️ Expired"
    expires = datetime.fromtimestamp(session.get('expires', 0))
    validated = datetime.fromtimestamp(session.get('last_validated', 0))

    return f"""
🔐 Session Info
══════════════════════
Status: {status}
Type: {session.get('type', 'unknown')}
Last validated: {validated.strftime('%Y-%m-%d %H:%M')}
Expires: {expires.strftime('%Y-%m-%d')}
"""

def format_help_message() -> str:
    """Format the help message"""
    return f"""
📱 INSTAGRAM DOWNLOADER BOT
══════════════════════════

🎯 QUICK START
------------------------------
• Simply paste any Instagram URL
• Bot will auto-detect and download

📋 AVAILABLE COMMANDS
------------------------------
├─ 🚀 /start - Start the bot
├─ 📊 /status - System status
├─ 🔐 /session - Manage login
├─ 🧹 /cleanup - Clear old files
╰─ ℹ️ /help - Show this help

📥 SUPPORTED CONTENT
------------------------------
├─ 📷 Posts & Carousels
├─ 🎬 Reels & Videos
├─ 📱 Stories*
╰─ ⭐ Highlights*

* Requires login

🔐 LOGIN OPTIONS
------------------------------
1️⃣ Upload Cookies:
   • Use /session upload
   • Send cookies.txt file

2️⃣ View Status:
   • Use /session status
   • Check login state

⚡️ TIPS
------------------------------
• Login for private content
• Use cleanup regularly
• Check status for issues

ℹ️ Need help? Contact @kelvitz716
"""