"""
Secrets Command - Secure management of Kubernetes secrets
"""

import json
import base64
import getpass
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime
from core.decorators import Command, arg
from core.logger import Logger
from core.colors import Colors
from utils.formatters import format_table


@Command.register("secrets", aliases=["secret"], help="Manage Kubernetes secrets", args=[
    arg("action", nargs="?", choices=[
        "list", "get", "create", "update", "delete", "decode",
        "encode", "copy", "backup", "restore", "rotate", "diff"
    ], help="Action to perform"),
    arg("name", nargs="?", help="Secret name"),

    # List options
    arg("-l", "--selector", help="Label selector"),
    arg("--show-values", action="store_true",
        help="Show decoded values (WARNING: insecure)"),
    arg("--show-keys", action="store_true", help="Show keys only"),
    arg("--type", help="Filter by secret type"),

    # Create/Update options
    arg("--from-literal", action="append",
        help="Key=value literal (can repeat)"),
    arg("--from-file", action="append",
        help="Key=filepath or filepath (can repeat)"),
    arg("--from-env-file", help="Load from .env file"),
    arg("--docker-registry", action="store_true",
        help="Create docker-registry secret"),
    arg("--docker-server", help="Docker registry server"),
    arg("--docker-username", help="Docker username"),
    arg("--docker-password", help="Docker password"),
    arg("--docker-email", help="Docker email"),
    arg("--tls-cert", help="TLS certificate file"),
    arg("--tls-key", help="TLS key file"),
    arg("--ssh-privatekey", help="SSH private key file"),
    arg("--basic-auth-user", help="Basic auth username"),
    arg("--basic-auth-password", help="Basic auth password"),

    # Get/Decode options
    arg("-k", "--key", help="Specific key to get/decode"),
    arg("--output-file", help="Output decoded value to file"),
    arg("--format", choices=["yaml", "json", "env"], default="yaml",
        help="Output format"),

    # Copy options
    arg("--to-namespace", help="Copy secret to this namespace"),
    arg("--new-name", help="New secret name when copying"),

    # Backup/Restore options
    arg("--backup-dir", help="Backup directory"),
    arg("--encrypt", action="store_true", help="Encrypt backup"),
    arg("--encryption-key", help="Encryption key for backup"),

    # Rotate options
    arg("--age", type=int, help="Rotate secrets older than N days"),
    arg("--dry-run", action="store_true", help="Show what would be done"),

    # Safety
    arg("--confirm", action="store_true", help="Skip confirmation prompts"),
    arg("--no-mask", action="store_true", help="Don't mask sensitive output"),
])
class SecretsCommand:
    """Secure management of Kubernetes secrets"""

    def __init__(self, kube):
        self.kube = kube

    def execute(self, args):
        """Execute secrets command"""
        action = args.action or "list"

        # Warning for show-values
        if args.show_values and not args.confirm:
            Logger.warn("WARNING: --show-values will display sensitive data!")
            response = input("Continue? [y/N]: ").strip().lower()
            if response not in ['y', 'yes']:
                Logger.info("Cancelled")
                return

        if action == "list":
            self.list_secrets(args)
        elif action == "get":
            self.get_secret(args)
        elif action == "create":
            self.create_secret(args)
        elif action == "update":
            self.update_secret(args)
        elif action == "delete":
            self.delete_secret(args)
        elif action == "decode":
            self.decode_secret(args)
        elif action == "encode":
            self.encode_value(args)
        elif action == "copy":
            self.copy_secret(args)
        elif action == "backup":
            self.backup_secrets(args)
        elif action == "restore":
            self.restore_secrets(args)
        elif action == "rotate":
            self.rotate_secrets(args)
        elif action == "diff":
            self.diff_secrets(args)

    def list_secrets(self, args):
        """List secrets"""
        cmd = ["get", "secrets", "-n", self.kube.namespace, "-o", "json"]

        if args.selector:
            cmd.extend(["-l", args.selector])

        result = self.kube.run(cmd)
        data = json.loads(result.stdout)

        secrets = []
        for item in data.get('items', []):
            secret_type = item.get('type', 'Opaque')

            # Filter by type if specified
            if args.type and args.type not in secret_type:
                continue

            secret_data = item.get('data', {})

            secrets.append({
                'name': item['metadata']['name'],
                'type': secret_type,
                'keys': len(secret_data),
                'age': self.get_age(item['metadata'].get('creationTimestamp', '')),
                'data': secret_data
            })

        if not secrets:
            print("No secrets found")
            return

        print(f"\n{Colors.BOLD}Secrets in {self.kube.namespace}{Colors.RESET}")
        print("=" * 80)

        if args.show_keys:
            self.display_with_keys(secrets, args)
        else:
            self.display_summary(secrets)

    def display_summary(self, secrets: List[Dict]):
        """Display secrets summary"""
        data = []
        for secret in secrets:
            data.append([
                secret['name'],
                secret['type'],
                str(secret['keys']),
                secret['age']
            ])

        print(format_table(data, ['NAME', 'TYPE', 'KEYS', 'AGE']))

    def display_with_keys(self, secrets: List[Dict], args):
        """Display secrets with keys"""
        for secret in secrets:
            print(f"\n{Colors.BOLD}{secret['name']}{Colors.RESET}")
            print(f"  Type: {secret['type']}")
            print(f"  Age: {secret['age']}")
            print(f"  Keys:")

            for key in secret['data'].keys():
                if args.show_values:
                    value = base64.b64decode(secret['data'][key]).decode(
                        'utf-8', errors='replace')
                    # Mask if not explicitly disabled
                    if not args.no_mask and len(value) > 20:
                        display_value = value[:10] + "..." + value[-10:]
                    else:
                        display_value = value
                    print(
                        f"    {Colors.YELLOW}{key}{Colors.RESET}: {display_value}")
                else:
                    print(
                        f"    {Colors.YELLOW}{key}{Colors.RESET}: <base64 encoded>")

    def get_secret(self, args):
        """Get specific secret"""
        if not args.name:
            Logger.error("Secret name required")
            return

        result = self.kube.run([
            "get", "secret", args.name,
            "-n", self.kube.namespace,
            "-o", "json"
        ])

        secret = json.loads(result.stdout)
        secret_data = secret.get('data', {})

        if args.key:
            # Get specific key
            if args.key not in secret_data:
                Logger.error(f"Key '{args.key}' not found in secret")
                return

            decoded = base64.b64decode(secret_data[args.key]).decode('utf-8')

            if args.output_file:
                Path(args.output_file).write_text(decoded)
                Logger.success(f"Saved to {args.output_file}")
            else:
                print(decoded)
        else:
            # Get all keys
            self.display_secret_data(secret, args)

    def display_secret_data(self, secret: Dict, args):
        """Display secret data"""
        secret_data = secret.get('data', {})

        print(f"\n{Colors.BOLD}{secret['metadata']['name']}{Colors.RESET}")
        print(f"Type: {secret.get('type', 'Opaque')}")
        print(f"Namespace: {secret['metadata']['namespace']}")
        print()

        if args.format == "yaml":
            self.display_yaml_format(secret_data)
        elif args.format == "json":
            self.display_json_format(secret_data)
        elif args.format == "env":
            self.display_env_format(secret_data)

    def display_yaml_format(self, data: Dict):
        """Display as YAML"""
        print("data:")
        for key, value in data.items():
            decoded = base64.b64decode(value).decode('utf-8', errors='replace')
            # Multi-line strings
            if '\n' in decoded:
                print(f"  {key}: |")
                for line in decoded.split('\n'):
                    print(f"    {line}")
            else:
                print(f"  {key}: {decoded}")

    def display_json_format(self, data: Dict):
        """Display as JSON"""
        decoded_data = {}
        for key, value in data.items():
            decoded_data[key] = base64.b64decode(
                value).decode('utf-8', errors='replace')
        print(json.dumps(decoded_data, indent=2))

    def display_env_format(self, data: Dict):
        """Display as env file format"""
        for key, value in data.items():
            decoded = base64.b64decode(value).decode('utf-8', errors='replace')
            # Quote if contains spaces
            if ' ' in decoded or '\n' in decoded:
                decoded = f'"{decoded}"'
            print(f"{key}={decoded}")

    def create_secret(self, args):
        """Create a new secret"""
        if not args.name:
            Logger.error("Secret name required")
            return

        if args.docker_registry:
            self.create_docker_secret(args)
        elif args.tls_cert and args.tls_key:
            self.create_tls_secret(args)
        elif args.ssh_privatekey:
            self.create_ssh_secret(args)
        elif args.basic_auth_user:
            self.create_basic_auth_secret(args)
        else:
            self.create_generic_secret(args)

    def create_generic_secret(self, args):
        """Create generic secret"""
        cmd = [
            "create", "secret", "generic", args.name,
            "-n", self.kube.namespace
        ]

        # From literals
        if args.from_literal:
            for literal in args.from_literal:
                cmd.append(f"--from-literal={literal}")

        # From files
        if args.from_file:
            for file_arg in args.from_file:
                cmd.append(f"--from-file={file_arg}")

        # From env file
        if args.from_env_file:
            cmd.append(f"--from-env-file={args.from_env_file}")

        # Check if we have any data
        if not (args.from_literal or args.from_file or args.from_env_file):
            Logger.error(
                "No secret data provided. Use --from-literal, --from-file, or --from-env-file")
            return

        Logger.info(f"Creating secret {args.name}...")
        self.kube.run(cmd, capture_output=False)
        Logger.success(f"Secret {args.name} created")

    def create_docker_secret(self, args):
        """Create docker-registry secret"""
        if not all([args.docker_server, args.docker_username]):
            Logger.error("--docker-server and --docker-username required")
            return

        # Get password if not provided
        password = args.docker_password
        if not password:
            password = getpass.getpass("Docker password: ")

        cmd = [
            "create", "secret", "docker-registry", args.name,
            "-n", self.kube.namespace,
            f"--docker-server={args.docker_server}",
            f"--docker-username={args.docker_username}",
            f"--docker-password={password}"
        ]

        if args.docker_email:
            cmd.append(f"--docker-email={args.docker_email}")

        Logger.info(f"Creating docker-registry secret {args.name}...")
        self.kube.run(cmd, capture_output=False)
        Logger.success(f"Docker secret {args.name} created")

    def create_tls_secret(self, args):
        """Create TLS secret"""
        if not Path(args.tls_cert).exists():
            Logger.error(f"Certificate file not found: {args.tls_cert}")
            return

        if not Path(args.tls_key).exists():
            Logger.error(f"Key file not found: {args.tls_key}")
            return

        cmd = [
            "create", "secret", "tls", args.name,
            "-n", self.kube.namespace,
            f"--cert={args.tls_cert}",
            f"--key={args.tls_key}"
        ]

        Logger.info(f"Creating TLS secret {args.name}...")
        self.kube.run(cmd, capture_output=False)
        Logger.success(f"TLS secret {args.name} created")

    def create_ssh_secret(self, args):
        """Create SSH secret"""
        if not Path(args.ssh_privatekey).exists():
            Logger.error(f"SSH key file not found: {args.ssh_privatekey}")
            return

        cmd = [
            "create", "secret", "generic", args.name,
            "-n", self.kube.namespace,
            f"--from-file=ssh-privatekey={args.ssh_privatekey}",
            "--type=kubernetes.io/ssh-auth"
        ]

        Logger.info(f"Creating SSH secret {args.name}...")
        self.kube.run(cmd, capture_output=False)
        Logger.success(f"SSH secret {args.name} created")

    def create_basic_auth_secret(self, args):
        """Create basic auth secret"""
        if not args.basic_auth_user:
            Logger.error("--basic-auth-user required")
            return

        password = args.basic_auth_password
        if not password:
            password = getpass.getpass("Password: ")

        cmd = [
            "create", "secret", "generic", args.name,
            "-n", self.kube.namespace,
            f"--from-literal=username={args.basic_auth_user}",
            f"--from-literal=password={password}",
            "--type=kubernetes.io/basic-auth"
        ]

        Logger.info(f"Creating basic-auth secret {args.name}...")
        self.kube.run(cmd, capture_output=False)
        Logger.success(f"Basic auth secret {args.name} created")

    def update_secret(self, args):
        """Update existing secret"""
        if not args.name:
            Logger.error("Secret name required")
            return

        # Get existing secret
        result = self.kube.run([
            "get", "secret", args.name,
            "-n", self.kube.namespace,
            "-o", "json"
        ])

        secret = json.loads(result.stdout)
        secret_data = secret.get('data', {})

        # Update with new values
        updated = False

        if args.from_literal:
            for literal in args.from_literal:
                key, value = literal.split('=', 1)
                secret_data[key] = base64.b64encode(value.encode()).decode()
                updated = True

        if args.from_file:
            for file_arg in args.from_file:
                if '=' in file_arg:
                    key, filepath = file_arg.split('=', 1)
                else:
                    filepath = file_arg
                    key = Path(filepath).name

                content = Path(filepath).read_bytes()
                secret_data[key] = base64.b64encode(content).decode()
                updated = True

        if not updated:
            Logger.error(
                "No updates provided. Use --from-literal or --from-file")
            return

        # Apply update
        secret['data'] = secret_data

        import tempfile
        import yaml

        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(secret, f)
            temp_file = f.name

        try:
            self.kube.run(["apply", "-f", temp_file], capture_output=False)
            Logger.success(f"Secret {args.name} updated")
        finally:
            Path(temp_file).unlink()

    def delete_secret(self, args):
        """Delete secret"""
        if not args.name:
            Logger.error("Secret name required")
            return

        if not args.confirm:
            response = input(
                f"Delete secret '{args.name}'? [y/N]: ").strip().lower()
            if response not in ['y', 'yes']:
                Logger.info("Cancelled")
                return

        self.kube.run([
            "delete", "secret", args.name,
            "-n", self.kube.namespace
        ], capture_output=False)

        Logger.success(f"Secret {args.name} deleted")

    def decode_secret(self, args):
        """Decode secret value"""
        if not args.name:
            Logger.error("Secret name required")
            return

        # Just call get_secret with show functionality
        self.get_secret(args)

    def encode_value(self, args):
        """Encode a value for secrets"""
        if args.name:
            # Encode provided value
            value = args.name
        else:
            # Read from stdin or prompt
            value = input("Enter value to encode: ")

        encoded = base64.b64encode(value.encode()).decode()
        print(f"\nBase64 encoded value:")
        print(encoded)

    def copy_secret(self, args):
        """Copy secret to another namespace"""
        if not args.name or not args.to_namespace:
            Logger.error("Secret name and --to-namespace required")
            return

        # Get source secret
        result = self.kube.run([
            "get", "secret", args.name,
            "-n", self.kube.namespace,
            "-o", "json"
        ])

        secret = json.loads(result.stdout)

        # Update metadata
        secret['metadata']['namespace'] = args.to_namespace
        if args.new_name:
            secret['metadata']['name'] = args.new_name

        # Remove runtime metadata
        secret['metadata'].pop('uid', None)
        secret['metadata'].pop('resourceVersion', None)
        secret['metadata'].pop('creationTimestamp', None)
        secret['metadata'].pop('selfLink', None)

        # Apply to target namespace
        import tempfile
        import yaml

        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(secret, f)
            temp_file = f.name

        try:
            self.kube.run(["apply", "-f", temp_file], capture_output=False)
            target_name = args.new_name or args.name
            Logger.success(
                f"Secret copied to {args.to_namespace}/{target_name}")
        finally:
            Path(temp_file).unlink()

    def backup_secrets(self, args):
        """Backup secrets"""
        backup_dir = Path(
            args.backup_dir or f"secrets-backup-{datetime.now().strftime('%Y%m%d-%H%M%S')}")
        backup_dir.mkdir(parents=True, exist_ok=True)

        Logger.info(f"Backing up secrets to {backup_dir}...")

        # Get all secrets
        result = self.kube.run([
            "get", "secrets",
            "-n", self.kube.namespace,
            "-o", "json"
        ])

        data = json.loads(result.stdout)

        import yaml

        for secret in data.get('items', []):
            name = secret['metadata']['name']

            # Skip service account tokens
            if secret.get('type') == 'kubernetes.io/service-account-token':
                continue

            # Clean metadata
            secret['metadata'].pop('uid', None)
            secret['metadata'].pop('resourceVersion', None)
            secret['metadata'].pop('creationTimestamp', None)
            secret['metadata'].pop('selfLink', None)
            secret['metadata'].pop('managedFields', None)

            # Save to file
            filepath = backup_dir / f"{name}.yaml"
            with open(filepath, 'w') as f:
                yaml.dump(secret, f)

        Logger.success(
            f"Backed up {len(data.get('items', []))} secrets to {backup_dir}")

    def restore_secrets(self, args):
        """Restore secrets from backup"""
        if not args.backup_dir:
            Logger.error("--backup-dir required")
            return

        backup_dir = Path(args.backup_dir)

        if not backup_dir.exists():
            Logger.error(f"Backup directory not found: {backup_dir}")
            return

        yaml_files = list(backup_dir.glob("*.yaml"))

        if not yaml_files:
            Logger.error("No YAML files found in backup directory")
            return

        Logger.info(f"Restoring {len(yaml_files)} secrets...")

        for filepath in yaml_files:
            try:
                self.kube.run(["apply", "-f", str(filepath)],
                              capture_output=True)
                Logger.success(f"Restored {filepath.stem}")
            except Exception as e:
                Logger.error(f"Failed to restore {filepath.stem}: {e}")

        Logger.success("Restore completed")

    def rotate_secrets(self, args):
        """Rotate old secrets"""
        Logger.info("Finding secrets to rotate...")

        # Implementation would check age and mark for rotation
        Logger.warn("Secret rotation requires manual intervention")
        Logger.info("Suggested workflow:")
        print("  1. Create new secret with updated values")
        print("  2. Update deployments to use new secret")
        print("  3. Verify applications work")
        print("  4. Delete old secret")

    def diff_secrets(self, args):
        """Compare two secrets"""
        if not args.name:
            Logger.error("Two secret names required (comma-separated)")
            Logger.info("Usage: secrets diff secret1,secret2")
            return

        names = args.name.split(',')
        if len(names) != 2:
            Logger.error("Exactly two secret names required")
            return

        # Get both secrets
        secrets_data = []
        for name in names:
            result = self.kube.run([
                "get", "secret", name.strip(),
                "-n", self.kube.namespace,
                "-o", "json"
            ])
            secret = json.loads(result.stdout)
            secrets_data.append({
                'name': name.strip(),
                'data': secret.get('data', {})
            })

        # Compare
        print(
            f"\n{Colors.BOLD}Comparing {names[0]} vs {names[1]}{Colors.RESET}")
        print("=" * 60)

        all_keys = set(secrets_data[0]['data'].keys()) | set(
            secrets_data[1]['data'].keys())

        for key in sorted(all_keys):
            val1 = secrets_data[0]['data'].get(key)
            val2 = secrets_data[1]['data'].get(key)

            if val1 and not val2:
                print(
                    f"{Colors.RED}- {key}{Colors.RESET} (only in {names[0]})")
            elif val2 and not val1:
                print(
                    f"{Colors.GREEN}+ {key}{Colors.RESET} (only in {names[1]})")
            elif val1 != val2:
                print(f"{Colors.YELLOW}~ {key}{Colors.RESET} (different values)")
            else:
                print(f"  {key} (identical)")

    def get_age(self, timestamp: str) -> str:
        """Get age from timestamp"""
        if not timestamp:
            return "unknown"

        try:
            from datetime import datetime, timezone
            created = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            now = datetime.now(timezone.utc)
            delta = now - created

            days = delta.days
            if days > 0:
                return f"{days}d"
            hours = delta.seconds // 3600
            if hours > 0:
                return f"{hours}h"
            minutes = (delta.seconds % 3600) // 60
            return f"{minutes}m"
        except:
            return "unknown"


# Usage examples
"""
# List all secrets
python k8s-mgr.py secrets list

# List with keys
python k8s-mgr.py secrets list --show-keys

# List with decoded values (DANGEROUS!)
python k8s-mgr.py secrets list --show-values

# Get specific secret
python k8s-mgr.py secrets get my-secret

# Get specific key
python k8s-mgr.py secrets get my-secret -k password

# Get as different formats
python k8s-mgr.py secrets get my-secret --format=json
python k8s-mgr.py secrets get my-secret --format=env

# Create from literals
python k8s-mgr.py secrets create my-secret \\
  --from-literal=username=admin \\
  --from-literal=password=secret123

# Create from files
python k8s-mgr.py secrets create app-secret \\
  --from-file=config.yaml \\
  --from-file=api-key=./key.txt

# Create from env file
python k8s-mgr.py secrets create env-secret --from-env-file=.env

# Create Docker registry secret
python k8s-mgr.py secrets create docker-secret \\
  --docker-registry \\
  --docker-server=docker.io \\
  --docker-username=myuser \\
  --docker-password=mypass

# Create TLS secret
python k8s-mgr.py secrets create tls-secret \\
  --tls-cert=server.crt \\
  --tls-key=server.key

# Create SSH secret
python k8s-mgr.py secrets create ssh-secret \\
  --ssh-privatekey=~/.ssh/id_rsa

# Create basic auth secret
python k8s-mgr.py secrets create auth-secret \\
  --basic-auth-user=admin \\
  --basic-auth-password=secret

# Update secret
python k8s-mgr.py secrets update my-secret \\
  --from-literal=password=newsecret123

# Decode specific key
python k8s-mgr.py secrets decode my-secret -k password

# Save decoded value to file
python k8s-mgr.py secrets get my-secret -k config --output-file=config.yaml

# Encode a value
python k8s-mgr.py secrets encode "my-secret-value"

# Copy secret to another namespace
python k8s-mgr.py secrets copy my-secret --to-namespace=production

# Copy with new name
python k8s-mgr.py secrets copy my-secret \\
  --to-namespace=staging \\
  --new-name=staging-secret

# Backup all secrets
python k8s-mgr.py secrets backup --backup-dir=./backup

# Restore secrets
python k8s-mgr.py secrets restore --backup-dir=./backup

# Compare two secrets
python k8s-mgr.py secrets diff secret1,secret2

# Delete secret
python k8s-mgr.py secrets delete my-secret

# Delete without confirmation
python k8s-mgr.py secrets delete my-secret --confirm
"""
