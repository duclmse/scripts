"""Resource cost estimation"""

from core.decorators import Command, arg
from core.logger import Logger


@Command.register("cost", help="Estimate resource costs", args=[
    arg("--cpu-cost", type=float, default=0.05, help="Cost per CPU hour"),
    arg("--memory-cost", type=float, default=0.01,
        help="Cost per GB memory hour"),
    arg("-l", "--selector", help="Label selector"),
])
class CostCommand:
    """Calculate cost estimates"""

    def __init__(self, kube):
        self.kube = kube

    def execute(self, args):
        cmd = ["get", "pods", "-n", self.kube.namespace, "-o", "json"]

        if args.selector:
            cmd.extend(["-l", args.selector])

        result = self.kube.run(cmd)

        import json
        data = json.loads(result.stdout)

        total_cpu = 0
        total_memory = 0

        print(f"Cost for namespace {self.kube.namespace}")
        print(f"{'POD':<40} {'CPU':<15} {'MEMORY':<15} {'COST/HOUR':<15}")
        print("-" * 85)

        for pod in data.get('items', []):
            pod_name = pod['metadata']['name']

            for container in pod['spec']['containers']:
                requests = container.get('resources', {}).get('requests', {})
                cpu = self.parse_cpu(requests.get('cpu', '0'))
                memory = self.parse_memory(requests.get('memory', '0'))

                total_cpu += cpu
                total_memory += memory

                cost_hour = (cpu * args.cpu_cost) + (memory * args.memory_cost)

                print(
                    f"{pod_name:<40} {cpu:<15.3f} {memory:<15.3f} ${cost_hour:<14.2f}")

        print("-" * 85)
        total_cost = (total_cpu * args.cpu_cost) + \
            (total_memory * args.memory_cost)
        print(
            f"{'TOTAL':<40} {total_cpu:<15.3f} {total_memory:<15.3f} ${total_cost:<14.2f}")
        print(f"\nEstimated monthly cost: ${total_cost * 24 * 30:.2f}")

    def parse_cpu(self, cpu_str: str) -> float:
        """Parse CPU string to cores"""
        if not cpu_str or cpu_str == '0':
            return 0
        if cpu_str.endswith('m'):
            return float(cpu_str[:-1]) / 1000
        return float(cpu_str)

    def parse_memory(self, mem_str: str) -> float:
        """Parse memory string to GB"""
        if not mem_str or mem_str == '0':
            return 0

        units = {'Ki': 1/1024/1024, 'Mi': 1/1024, 'Gi': 1, 'Ti': 1024}

        for unit, multiplier in units.items():
            if mem_str.endswith(unit):
                return float(mem_str[:-2]) * multiplier

        return float(mem_str) / (1024**3)  # Assume bytes
