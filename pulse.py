#!/usr/bin/env python3
"""
Pulse — красивый живой дашборд в терминале.
"""

import time
import psutil
from datetime import datetime
from rich.console import Console, Group
from rich.live import Live
from rich.table import Table
from rich.panel import Panel
from rich.layout import Layout
from rich.progress import Progress, BarColumn, TextColumn, SpinnerColumn
from rich.text import Text
from rich import box
from rich.align import Align

console = Console()


def make_bar(percent: float, width: int = 20) -> str:
    """Создаёт текстовый прогресс-бар."""
    filled = int(width * percent / 100)
    bar = "█" * filled + "░" * (width - filled)
    if percent > 85:
        color = "red"
    elif percent > 60:
        color = "yellow"
    else:
        color = "green"
    return f"[{color}]{bar}[/{color}] {percent:5.1f}%"


def get_cpu_panel() -> Panel:
    cpu_percent = psutil.cpu_percent(interval=None)
    cpu_count = psutil.cpu_count(logical=True)
    cpu_freq = psutil.cpu_freq()

    freq_text = f"{cpu_freq.current:.0f} MHz" if cpu_freq else "N/A"

    content = Text()
    content.append("\n")
    content.append(f"  Использование:  ", style="bold")
    content.append(Text.from_markup(make_bar(cpu_percent)))
    content.append("\n\n")
    content.append(f"  Ядра: {cpu_count}    Частота: {freq_text}\n", style="dim")

    # Нагрузка по ядрам
    per_cpu = psutil.cpu_percent(percpu=True)
    cores_line = "  "
    for i, p in enumerate(per_cpu):
        if p > 80:
            style = "red"
        elif p > 50:
            style = "yellow"
        else:
            style = "green"
        cores_line += f"[{style}]●[/{style}] "
    content.append(Text.from_markup(cores_line + "\n"))

    return Panel(content, title="[bold cyan]CPU[/bold cyan]", border_style="cyan", box=box.ROUNDED)


def get_memory_panel() -> Panel:
    mem = psutil.virtual_memory()
    swap = psutil.swap_memory()

    content = Text()
    content.append("\n")
    content.append("  RAM:  ", style="bold")
    content.append(Text.from_markup(make_bar(mem.percent)))
    content.append(f"\n  {mem.used // (1024**3):.1f} / {mem.total // (1024**3):.1f} GB\n\n", style="dim")

    content.append("  Swap: ", style="bold")
    content.append(Text.from_markup(make_bar(swap.percent)))
    content.append(f"\n  {swap.used // (1024**3):.1f} / {swap.total // (1024**3):.1f} GB\n", style="dim")

    return Panel(content, title="[bold magenta]Память[/bold magenta]", border_style="magenta", box=box.ROUNDED)


def get_disk_panel() -> Panel:
    content = Text("\n")

    for part in psutil.disk_partitions(all=False):
        if part.fstype and not part.mountpoint.startswith("/snap"):
            try:
                usage = psutil.disk_usage(part.mountpoint)
                content.append(f"  {part.mountpoint:<12} ", style="bold")
                content.append(Text.from_markup(make_bar(usage.percent, width=15)))
                content.append(f"  {usage.used // (1024**3):.0f}/{usage.total // (1024**3):.0f} GB\n", style="dim")
            except PermissionError:
                continue

    return Panel(content, title="[bold yellow]Диски[/bold yellow]", border_style="yellow", box=box.ROUNDED)


def get_network_panel() -> Panel:
    net = psutil.net_io_counters()
    content = Text()
    content.append("\n")
    content.append(f"  Отправлено:   {net.bytes_sent / (1024**2):.1f} MB\n", style="green")
    content.append(f"  Получено:    {net.bytes_recv / (1024**2):.1f} MB\n", style="blue")
    content.append(f"  Пакетов ↑:   {net.packets_sent:,}\n", style="dim")
    content.append(f"  Пакетов ↓:   {net.packets_recv:,}\n", style="dim")

    return Panel(content, title="[bold blue]Сеть[/bold blue]", border_style="blue", box=box.ROUNDED)


def get_processes_table() -> Table:
    table = Table(
        title="Топ процессов",
        box=box.SIMPLE_HEAVY,
        show_header=True,
        header_style="bold",
        expand=True,
    )
    table.add_column("PID", style="dim", width=8)
    table.add_column("Имя", style="cyan", ratio=2)
    table.add_column("CPU %", justify="right", width=8)
    table.add_column("RAM %", justify="right", width=8)
    table.add_column("Статус", width=10)

    processes = []
    for proc in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent", "status"]):
        try:
            info = proc.info
            processes.append(info)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    # Сортируем по CPU
    processes.sort(key=lambda x: x.get("cpu_percent") or 0, reverse=True)

    for p in processes[:8]:
        cpu = p.get("cpu_percent") or 0
        mem = p.get("memory_percent") or 0
        status = p.get("status") or "—"

        cpu_style = "red" if cpu > 50 else "yellow" if cpu > 20 else "green"
        mem_style = "red" if mem > 30 else "yellow" if mem > 15 else "white"

        table.add_row(
            str(p["pid"]),
            (p["name"] or "?")[:22],
            f"[{cpu_style}]{cpu:.1f}[/{cpu_style}]",
            f"[{mem_style}]{mem:.1f}[/{mem_style}]",
            status[:9],
        )

    return table


def get_header() -> Panel:
    now = datetime.now().strftime("%H:%M:%S")
    boot = datetime.fromtimestamp(psutil.boot_time())
    uptime = datetime.now() - boot
    hours, remainder = divmod(int(uptime.total_seconds()), 3600)
    minutes, _ = divmod(remainder, 60)

    text = Text()
    text.append("  PULSE", style="bold white")
    text.append("  ·  ", style="dim")
    text.append(f"{now}", style="cyan")
    text.append("  ·  ", style="dim")
    text.append(f"Аптайм: {hours}ч {minutes}м", style="dim")
    text.append("  ·  ", style="dim")
    text.append("q — выход", style="dim italic")

    return Panel(Align.center(text), style="bold", border_style="bright_blue", box=box.DOUBLE)


def generate_dashboard() -> Layout:
    layout = Layout()

    layout.split_column(
        Layout(name="header", size=3),
        Layout(name="body"),
        Layout(name="footer", size=12),
    )

    layout["body"].split_row(
        Layout(name="left"),
        Layout(name="right"),
    )

    layout["left"].split_column(
        Layout(name="cpu"),
        Layout(name="memory"),
    )

    layout["right"].split_column(
        Layout(name="disk"),
        Layout(name="network"),
    )

    layout["header"].update(get_header())
    layout["cpu"].update(get_cpu_panel())
    layout["memory"].update(get_memory_panel())
    layout["disk"].update(get_disk_panel())
    layout["network"].update(get_network_panel())
    layout["footer"].update(Panel(get_processes_table(), border_style="dim", box=box.ROUNDED))

    return layout


def main():
    # Первый вызов cpu_percent, чтобы следующие были корректными
    psutil.cpu_percent(interval=None)
    time.sleep(0.3)

    console.clear()
    console.print("[bold green]Запуск Pulse...[/bold green]")
    time.sleep(0.4)

    try:
        with Live(generate_dashboard(), console=console, refresh_per_second=0.8, screen=True) as live:
            while True:
                time.sleep(1.5)
                live.update(generate_dashboard())
    except KeyboardInterrupt:
        console.print("\n[yellow]Pulse остановлен. До встречи![/yellow]")


if __name__ == "__main__":
    main()
