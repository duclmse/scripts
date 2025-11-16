import xml.etree.ElementTree as ET
import argparse
from collections import defaultdict
from typing import Dict, List, Tuple
from dataclasses import dataclass, field


@dataclass
class CoverageMetrics:
    """Store coverage metrics for instructions, branches, lines, etc."""
    instruction_missed: int = 0
    instruction_covered: int = 0
    branch_missed: int = 0
    branch_covered: int = 0
    line_missed: int = 0
    line_covered: int = 0
    complexity_missed: int = 0
    complexity_covered: int = 0
    method_missed: int = 0
    method_covered: int = 0
    class_missed: int = 0
    class_covered: int = 0

    def add(self, other: 'CoverageMetrics'):
        """Add another CoverageMetrics to this one."""
        self.instruction_missed += other.instruction_missed
        self.instruction_covered += other.instruction_covered
        self.branch_missed += other.branch_missed
        self.branch_covered += other.branch_covered
        self.line_missed += other.line_missed
        self.line_covered += other.line_covered
        self.complexity_missed += other.complexity_missed
        self.complexity_covered += other.complexity_covered
        self.method_missed += other.method_missed
        self.method_covered += other.method_covered
        self.class_missed += other.class_missed
        self.class_covered += other.class_covered

    def get_percentage(self, covered: int, missed: int) -> float:
        """Calculate coverage percentage."""
        total = covered + missed
        return (covered / total * 100) if total > 0 else 0.0

    @property
    def instruction_coverage(self) -> float:
        return self.get_percentage(self.instruction_covered, self.instruction_missed)

    @property
    def branch_coverage(self) -> float:
        return self.get_percentage(self.branch_covered, self.branch_missed)

    @property
    def line_coverage(self) -> float:
        return self.get_percentage(self.line_covered, self.line_missed)

    @property
    def method_coverage(self) -> float:
        return self.get_percentage(self.method_covered, self.method_missed)

    @property
    def class_coverage(self) -> float:
        return self.get_percentage(self.class_covered, self.class_missed)


class JacocoParser:
    def __init__(self, xml_file: str):
        """
        Initialize the parser with a JaCoCo XML report file.

        Args:
            xml_file: Path to the JaCoCo XML report
        """
        self.xml_file = xml_file
        self.tree = ET.parse(xml_file)
        self.root = self.tree.getroot()
        self.package_metrics: Dict[str, CoverageMetrics] = {}

    def parse_counter(self, counter_elem) -> Tuple[str, int, int]:
        """
        Parse a counter element from JaCoCo XML.

        Args:
            counter_elem: XML element for a counter

        Returns:
            Tuple of (type, missed, covered)
        """
        counter_type = counter_elem.get('type')
        missed = int(counter_elem.get('missed', 0))
        covered = int(counter_elem.get('covered', 0))
        return counter_type, missed, covered

    def parse_package(self, package_elem) -> Tuple[str, CoverageMetrics]:
        """
        Parse a package element and extract coverage metrics.

        Args:
            package_elem: XML element for a package

        Returns:
            Tuple of (package_name, CoverageMetrics)
        """
        package_name = package_elem.get('name', '')
        metrics = CoverageMetrics()

        # Parse all counters in the package
        for counter in package_elem.findall('counter'):
            counter_type, missed, covered = self.parse_counter(counter)

            if counter_type == 'INSTRUCTION':
                metrics.instruction_missed = missed
                metrics.instruction_covered = covered
            elif counter_type == 'BRANCH':
                metrics.branch_missed = missed
                metrics.branch_covered = covered
            elif counter_type == 'LINE':
                metrics.line_missed = missed
                metrics.line_covered = covered
            elif counter_type == 'COMPLEXITY':
                metrics.complexity_missed = missed
                metrics.complexity_covered = covered
            elif counter_type == 'METHOD':
                metrics.method_missed = missed
                metrics.method_covered = covered
            elif counter_type == 'CLASS':
                metrics.class_missed = missed
                metrics.class_covered = covered

        return package_name, metrics

    def get_parent_package(self, package_name: str) -> str:
        """
        Extract parent package from full package name.

        Args:
            package_name: Full package name (e.g., 'com/example/service/impl')

        Returns:
            Parent package name (e.g., 'com/example/service')
        """
        if '/' not in package_name:
            return package_name

        parts = package_name.split('/')
        # Return the first level package or first two levels
        # You can adjust this logic based on your needs
        return parts[0] if len(parts) == 1 else '/'.join(parts[:2])

    def aggregate_by_parent_package(self, depth: int = 1) -> Dict[str, CoverageMetrics]:
        """
        Aggregate coverage metrics by parent package.

        Args:
            depth: Number of package levels to aggregate (1 = top level, 2 = second level, etc.)

        Returns:
            Dictionary mapping parent package names to aggregated metrics
        """
        parent_metrics: Dict[str, CoverageMetrics] = defaultdict(
            CoverageMetrics)

        # Find all package elements
        for package in self.root.findall('.//package'):
            package_name, metrics = self.parse_package(package)

            # Get parent package at specified depth
            parts = package_name.split('/')
            if len(parts) >= depth:
                parent_name = '/'.join(parts[:depth])
            else:
                parent_name = package_name

            # Aggregate metrics
            if parent_name not in parent_metrics:
                parent_metrics[parent_name] = CoverageMetrics()
            parent_metrics[parent_name].add(metrics)

        return dict(parent_metrics)

    def print_summary(self, depth: int = 1, sort_by: str = 'name'):
        """
        Print aggregated coverage summary to console.

        Args:
            depth: Package depth for aggregation
            sort_by: Sort by 'name', 'instruction', 'branch', 'line', 'method', 'class'
        """
        parent_metrics = self.aggregate_by_parent_package(depth)

        if not parent_metrics:
            print("No package data found in the JaCoCo report.")
            return

        # Sort packages
        if sort_by == 'name':
            sorted_packages = sorted(parent_metrics.items())
        elif sort_by == 'instruction':
            sorted_packages = sorted(parent_metrics.items(),
                                     key=lambda x: x[1].instruction_coverage,
                                     reverse=True)
        elif sort_by == 'branch':
            sorted_packages = sorted(parent_metrics.items(),
                                     key=lambda x: x[1].branch_coverage,
                                     reverse=True)
        elif sort_by == 'line':
            sorted_packages = sorted(parent_metrics.items(),
                                     key=lambda x: x[1].line_coverage,
                                     reverse=True)
        elif sort_by == 'method':
            sorted_packages = sorted(parent_metrics.items(),
                                     key=lambda x: x[1].method_coverage,
                                     reverse=True)
        elif sort_by == 'class':
            sorted_packages = sorted(parent_metrics.items(),
                                     key=lambda x: x[1].class_coverage,
                                     reverse=True)
        else:
            sorted_packages = sorted(parent_metrics.items())

        # Print header
        print("\n" + "="*120)
        print(
            f"JaCoCo Coverage Report - Aggregated by Parent Package (Depth: {depth})")
        print("="*120)
        print(f"{'Package':<40} {'Instructions':>15} {'Branches':>15} {'Lines':>12} {'Methods':>12} {'Classes':>12}")
        print("-"*120)

        i = 0
        # Print each package
        for package_name, metrics in sorted_packages:
            i += 1
            inst_total = metrics.instruction_covered + metrics.instruction_missed
            branch_total = metrics.branch_covered + metrics.branch_missed
            line_total = metrics.line_covered + metrics.line_missed
            method_total = metrics.method_covered + metrics.method_missed
            class_total = metrics.class_covered + metrics.class_missed

            print(f"{i:>2} {package_name:<40} "
                  #   f"{metrics.instruction_coverage:>6.1f}% "
                  #   f"({metrics.instruction_covered:>5}/{inst_total:<5}) "
                  #   f"{metrics.branch_coverage:>6.1f}% "
                  # f"({metrics.branch_covered:>4}/{branch_total:<4}) "
                  #   f"{metrics.line_coverage:>6.1f}% "
                  #   f"({metrics.line_covered:>4}/{line_total:<4}) "
                  f"{line_total:<4} "
                  #   f"{metrics.method_coverage:>6.1f}% "
                  #   f"({metrics.method_covered:>3}/{method_total:<3}) "
                  #   f"{metrics.class_coverage:>6.1f}% "
                  #   f"({metrics.class_covered:>2}/{class_total:<2})"
                  )
        print("-"*120)

        # Calculate overall totals
        total_metrics = CoverageMetrics()
        for metrics in parent_metrics.values():
            total_metrics.add(metrics)

        inst_total = total_metrics.instruction_covered + total_metrics.instruction_missed
        branch_total = total_metrics.branch_covered + total_metrics.branch_missed
        line_total = total_metrics.line_covered + total_metrics.line_missed
        method_total = total_metrics.method_covered + total_metrics.method_missed
        class_total = total_metrics.class_covered + total_metrics.class_missed

        print(f"{'TOTAL':<40} "
              f"{total_metrics.instruction_coverage:>6.1f}% "
              f"({total_metrics.instruction_covered:>5}/{inst_total:<5}) "
              f"{total_metrics.branch_coverage:>6.1f}% "
              f"({total_metrics.branch_covered:>4}/{branch_total:<4}) "
              f"{total_metrics.line_coverage:>6.1f}% "
              f"({total_metrics.line_covered:>4}/{line_total:<4}) "
              f"{total_metrics.method_coverage:>6.1f}% "
              f"({total_metrics.method_covered:>3}/{method_total:<3}) "
              f"{total_metrics.class_coverage:>6.1f}% "
              f"({total_metrics.class_covered:>2}/{class_total:<2})")
        print("="*120 + "\n")


def main():
    parser = argparse.ArgumentParser(
        description='Parse JaCoCo XML report and display aggregated coverage by parent package'
    )
    parser.add_argument(
        'xml_file', help='Path to JaCoCo XML report (e.g., jacoco.xml)')
    parser.add_argument(
        '--depth',
        type=int,
        default=1,
        help='Package depth for aggregation (default: 1 = top-level packages)'
    )
    parser.add_argument(
        '--sort',
        choices=['name', 'instruction', 'branch', 'line', 'method', 'class'],
        default='name',
        help='Sort packages by specified metric (default: name)'
    )

    args = parser.parse_args()

    try:
        jacoco = JacocoParser(args.xml_file)
        jacoco.print_summary(depth=args.depth, sort_by=args.sort)
    except FileNotFoundError:
        print(f"Error: File '{args.xml_file}' not found.")
    except ET.ParseError as e:
        print(f"Error parsing XML file: {e}")
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    main()
