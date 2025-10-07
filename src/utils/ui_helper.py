"""
UI Helper utilities for formatting bot messages and responses.
"""
import os
import psutil
import platform
from datetime import datetime
from typing import Dict, Any, Optional

def format_bytes(size: int) -> str:
    """Format bytes into human readable format"""
    units = ["B", "KB", "MB", "GB", "TB"]
    unit_index = 0
    while size >= 1024 and unit_index < len(units) - 1:
        size /= 1024
        unit_index += 1
    return f"{size:.1f}{units[unit_index]}"

def format_duration(seconds: float) -> str:
    """Format duration in seconds to human readable format"""
    if not seconds:
        return "0s"
    
    if seconds < 60:
        return f"{seconds:.1f}s"
    
    minutes = int(seconds // 60)
    remaining_seconds = seconds % 60
    
    if minutes < 60:
        return f"{minutes}m {remaining_seconds:.1f}s"
    
    hours = minutes // 60
    remaining_minutes = minutes % 60
    
    return f"{hours}h {remaining_minutes}m"

def format_job_progress(job_id: str, downloaded: int, uploaded: int, failed: int, total: int,
                       duration: Optional[float] = None, error: Optional[str] = None,
                       post_info: Optional[Dict[str, Any]] = None,
                       is_complete: Optional[bool] = None,
                       status_override: Optional[str] = None) -> str:
    """Format job progress message"""
    if is_complete is None:
        is_complete = uploaded + failed == total
    
    progress = (uploaded / total * 100) if total > 0 else 0
    pending = total - (uploaded + failed)
    speed = (uploaded / duration) if duration and duration > 0 else 0

    # Status text
    if status_override:
        status = status_override
    elif error:
        status = "[X] ERROR"
    elif is_complete:
        status = "[+] UPLOAD COMPLETE" if uploaded == total else "[!] PARTIALLY COMPLETE"
    else:
        status = "[>] UPLOADING"

    # Build message
    lines = [status, f"[#] Job: {job_id}", ""]
    
    if post_info:
        lines.extend([
            f"[U] From: @{post_info.get('author', 'unknown')}",
            f"[<3] Likes: {post_info.get('likes', 0):,}",
            ""
        ])

    lines.extend([
        f"[T] Time: {format_duration(duration) if duration else 'Just started'}",
        f"[*] Progress: {progress:.1f}% ({uploaded}/{total})"
    ])
    
    if not is_complete and speed > 0:
        lines.append(f"[>] Speed: {speed:.1f} files/sec")

    if failed > 0:
        lines.append(f"[X] Failed: {failed}")
    if pending > 0:
        lines.append(f"[~] Remaining: {pending}")
        
    if error:
        lines.extend(["", f"[X] Error: {error}"])
    elif is_complete and uploaded == total:
        lines.extend(["", "[*] All files processed successfully!"])
    elif is_complete:
        lines.extend(["", f"[+] Complete: {uploaded}/{total} files uploaded"])

    return "\n".join(lines)

def format_media_caption(filename: str, number: int, total: int, media_info: Dict[str, Any]) -> str:
    """Format media file upload caption"""
    lines = [f"[+] Media {number}/{total}"]
    
    size = media_info.get("size")
    if size:
        size_str = format_bytes(int(size))
        lines.append(f"[#] Size: {size_str}")
        
    width = media_info.get("width")
    height = media_info.get("height")
    if width and height:
        lines.append(f"[R] Resolution: {width}x{height}")
        
    return "\n".join(lines)

def format_help_message() -> str:
    """Format the help message"""
    return """
[APP] INSTAGRAM DOWNLOADER BOT
============================

Simply paste any Instagram URL to download content.
The bot will automatically detect and process the media.

[MENU] COMMANDS:
/start - Start the bot
/status - Check system status
/help - Show this help message
"""

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
[STATUS] MISSION STATUS REPORT
============================
Report Time: {datetime.now().strftime('%b %d, %Y at %I:%M %p')}

[SYS] SYSTEM VITALS
----------------------------
- [FD] Open FDs    : {system['open_fds']}
- [CPU] Usage   : {system['cpu_time']:.1f}s total
- [TIME] Uptime : {format_duration(system['uptime'])}

[MEM] MEMORY STATUS
----------------------------
- [V] Virtual Mem : {format_bytes(system['memory_virtual'])}
- [U] Memory Used : {format_bytes(system['memory_used'])}

[STATS] DOWNLOAD STATS
----------------------------
- [D] Downloaded : {stats.get('total_downloaded', 0)}
- [U] Uploaded   : {stats.get('total_uploaded', 0)}
- [F] Failed     : {stats.get('total_failed', 0)}
- [S] Total Size : {format_bytes(stats.get('total_size', 0))}

[ENV] RUNTIME ENVIRONMENT
----------------------------
- [R] Runtime : {system['runtime']} {system['version']}
- [S] Status  : {'[OK] Online' if metrics.get('healthy', True) else '[!] Warning'}

----------------------------
[*] Status Indicators:
[OK] Normal | [!] Warning | [X] Critical

This is an automated health report
"""
