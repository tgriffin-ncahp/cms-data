"""CLI for browsing CMS Medicaid data interfaces."""

from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.table import Table

from .api import CmsMedicaidClient
from .models import Dataset

console = Console()


def truncate(text: str, max_length: int = 60) -> str:
    """Truncate text to max length with ellipsis."""
    if len(text) <= max_length:
        return text
    return text[: max_length - 3] + "..."


def format_dataset_row(dataset: Dataset) -> tuple:
    """Format a dataset for table display."""
    return (
        dataset.identifier[:8] + "...",
        truncate(dataset.title, 50),
        dataset.modified or "N/A",
        str(len(dataset.distributions)),
    )


@click.group()
@click.version_option(version="0.1.0")
def main():
    """CMS Medicaid Data Browser - Browse and query CMS Medicaid datasets."""
    pass


@main.command()
@click.option("--search", "-s", help="Search term to filter datasets")
@click.option("--theme", "-t", help="Filter by theme/category")
@click.option("--limit", "-l", default=20, help="Maximum datasets to show")
@click.option("--refresh", is_flag=True, help="Force refresh catalog cache")
def catalog(search: Optional[str], theme: Optional[str], limit: int, refresh: bool):
    """List available datasets from the CMS Medicaid data portal."""
    with CmsMedicaidClient() as client:
        try:
            cat = client.fetch_catalog(force_refresh=refresh)
            datasets = cat.datasets

            if search:
                datasets = [d for d in datasets if d.matches_search(search)]

            if theme:
                datasets = [
                    d
                    for d in datasets
                    if any(theme.lower() in t.lower() for t in d.themes)
                ]

            table = Table(title=f"CMS Medicaid Datasets ({len(datasets)} found)")
            table.add_column("ID", style="cyan", no_wrap=True)
            table.add_column("Title", style="green")
            table.add_column("Modified", style="yellow")
            table.add_column("Files", style="magenta")

            for dataset in datasets[:limit]:
                table.add_row(*format_dataset_row(dataset))

            console.print(table)

            if len(datasets) > limit:
                console.print(
                    f"\n[dim]Showing {limit} of {len(datasets)} datasets. "
                    f"Use --limit to see more.[/dim]"
                )

        except Exception as e:
            console.print(f"[red]Error fetching catalog: {e}[/red]")
            raise SystemExit(1)


@main.command()
@click.argument("dataset_id")
def info(dataset_id: str):
    """Show detailed information about a dataset."""
    with CmsMedicaidClient() as client:
        try:
            cat = client.fetch_catalog()

            dataset = None
            for d in cat.datasets:
                if d.identifier == dataset_id or d.identifier.startswith(dataset_id):
                    dataset = d
                    break

            if not dataset:
                console.print(f"[red]Dataset not found: {dataset_id}[/red]")
                raise SystemExit(1)

            console.print(f"\n[bold cyan]{dataset.title}[/bold cyan]")
            console.print(f"[dim]ID: {dataset.identifier}[/dim]\n")

            console.print(f"[bold]Description:[/bold]")
            console.print(f"{dataset.description}\n")

            console.print(f"[bold]Metadata:[/bold]")
            console.print(f"  Access Level: {dataset.access_level}")
            console.print(f"  Modified: {dataset.modified}")
            if dataset.issued:
                console.print(f"  Issued: {dataset.issued}")
            if dataset.temporal:
                console.print(f"  Temporal: {dataset.temporal}")
            if dataset.accrual_periodicity:
                console.print(f"  Update Frequency: {dataset.accrual_periodicity}")

            if dataset.publisher:
                console.print(f"  Publisher: {dataset.publisher.name}")

            if dataset.contact_point:
                console.print(
                    f"  Contact: {dataset.contact_point.fn} ({dataset.contact_point.email})"
                )

            if dataset.keywords:
                console.print(f"\n[bold]Keywords:[/bold] {', '.join(dataset.keywords)}")

            if dataset.themes:
                console.print(f"[bold]Themes:[/bold] {', '.join(dataset.themes)}")

            if dataset.distributions:
                console.print(f"\n[bold]Distributions ({len(dataset.distributions)}):[/bold]")
                for dist in dataset.distributions:
                    url = dist.download_url or dist.access_url or "N/A"
                    console.print(f"  - {dist.title} [{dist.format}]")
                    console.print(f"    [dim]{url}[/dim]")

        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")
            raise SystemExit(1)


@main.command()
@click.argument("dataset_id")
def distributions(dataset_id: str):
    """List data files available for a dataset."""
    with CmsMedicaidClient() as client:
        try:
            cat = client.fetch_catalog()

            dataset = None
            for d in cat.datasets:
                if d.identifier == dataset_id or d.identifier.startswith(dataset_id):
                    dataset = d
                    break

            if not dataset:
                console.print(f"[red]Dataset not found: {dataset_id}[/red]")
                raise SystemExit(1)

            if not dataset.distributions:
                console.print("[yellow]No distributions found for this dataset.[/yellow]")
                return

            table = Table(title=f"Distributions for: {truncate(dataset.title, 40)}")
            table.add_column("Title", style="green")
            table.add_column("Format", style="cyan")
            table.add_column("URL", style="dim")

            for dist in dataset.distributions:
                url = dist.download_url or dist.access_url or "N/A"
                table.add_row(dist.title, dist.format, truncate(url, 60))

            console.print(table)

        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")
            raise SystemExit(1)


@main.command()
@click.argument("dataset_id")
@click.option("--limit", "-l", default=10, help="Number of records to fetch")
@click.option("--offset", "-o", default=0, help="Number of records to skip")
@click.option(
    "--format",
    "-f",
    "output_format",
    type=click.Choice(["table", "json", "csv"]),
    default="table",
    help="Output format",
)
def query(dataset_id: str, limit: int, offset: int, output_format: str):
    """Query data from a dataset."""
    with CmsMedicaidClient() as client:
        try:
            cat = client.fetch_catalog()

            dataset = None
            for d in cat.datasets:
                if d.identifier == dataset_id or d.identifier.startswith(dataset_id):
                    dataset = d
                    break

            if not dataset:
                console.print(f"[red]Dataset not found: {dataset_id}[/red]")
                raise SystemExit(1)

            console.print(f"[dim]Querying: {dataset.title}[/dim]\n")

            df = client.query(dataset.identifier, limit=limit, offset=offset)

            if df.empty:
                console.print("[yellow]No data returned from query.[/yellow]")
                console.print(
                    "[dim]This dataset may not support datastore queries. "
                    "Try downloading the distribution files instead.[/dim]"
                )
                return

            if output_format == "json":
                print(df.to_json(orient="records", indent=2))
            elif output_format == "csv":
                print(df.to_csv(index=False))
            else:
                table = Table(title=f"Query Results ({len(df)} rows)")
                for col in df.columns[:10]:
                    table.add_column(str(col), overflow="fold")

                for _, row in df.head(limit).iterrows():
                    values = [truncate(str(v), 30) for v in row.values[:10]]
                    table.add_row(*values)

                console.print(table)

                if len(df.columns) > 10:
                    console.print(
                        f"[dim]Showing 10 of {len(df.columns)} columns.[/dim]"
                    )

        except Exception as e:
            console.print(f"[red]Error querying data: {e}[/red]")
            raise SystemExit(1)


@main.command()
@click.argument("url")
@click.option("--output", "-o", type=click.Path(), help="Output file path")
def download(url: str, output: Optional[str]):
    """Download a distribution file."""
    with CmsMedicaidClient() as client:
        try:
            output_path = Path(output) if output else None
            result = client.download(url, output_path)
            console.print(f"[green]Downloaded to: {result}[/green]")
        except Exception as e:
            console.print(f"[red]Error downloading: {e}[/red]")
            raise SystemExit(1)


@main.command()
def themes():
    """List all available themes/categories."""
    with CmsMedicaidClient() as client:
        try:
            all_themes = client.list_themes()

            if not all_themes:
                console.print("[yellow]No themes found.[/yellow]")
                return

            console.print(f"[bold]Available Themes ({len(all_themes)}):[/bold]\n")
            for theme in all_themes:
                console.print(f"  - {theme}")

        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")
            raise SystemExit(1)


@main.command()
def keywords():
    """List all available keywords/tags."""
    with CmsMedicaidClient() as client:
        try:
            all_keywords = client.list_keywords()

            if not all_keywords:
                console.print("[yellow]No keywords found.[/yellow]")
                return

            console.print(f"[bold]Available Keywords ({len(all_keywords)}):[/bold]\n")

            for i in range(0, len(all_keywords), 3):
                row = all_keywords[i : i + 3]
                console.print("  " + " | ".join(row))

        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")
            raise SystemExit(1)


if __name__ == "__main__":
    main()
