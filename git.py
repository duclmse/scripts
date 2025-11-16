#!/usr/bin/env python3
"""
Git Repository Manager - Advanced multi-repository management tool
Version: 2.0.0
"""

import argparse
import json
import logging
import os
import re
import shutil
import subprocess
import sys
import tarfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse

# Color codes for terminal output
class Colors:
    RED = '\033[0;31m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    BLUE = '\033[0;34m'
    BOLD = '\033[1m'
    NC = '\033[0m'  # No Color

@dataclass
class RepoConfig:
    """Repository configuration"""
    repo: str
    folder: Optional[str] = None
    branch: Optional[str] = None
    
    @property
    def target_folder(self) -> str:
        """Get target folder name"""
        if self.folder:
            return self.folder
        return Path(self.repo).stem.replace('.git', '')

@dataclass
class Statistics:
    """Operation statistics"""
    total: int = 0
    success: int = 0
    failed: int = 0
    skipped: int = 0
    
    def print_summary(self, logger):
        """Print statistics summary"""
        logger.info("=" * 50)
        logger.info("Summary:")
        logger.info(f"{Colors.GREEN}  Successful: {self.success}{Colors.NC}")
        logger.info(f"{Colors.RED}  Failed: {self.failed}{Colors.NC}")
        logger.info(f"{Colors.YELLOW}  Skipped: {self.skipped}{Colors.NC}")
        logger.info(f"  Total: {self.total}")
        logger.info("=" * 50)

class ColoredFormatter(logging.Formatter):
    """Custom formatter with colors"""
    
    COLORS = {
        'DEBUG': Colors.BLUE,
        'INFO': Colors.BLUE,
        'WARNING': Colors.YELLOW,
        'ERROR': Colors.RED,
        'CRITICAL': Colors.RED + Colors.BOLD,
        'SUCCESS': Colors.GREEN,
    }
    
    def format(self, record):
        # Add color to level name
        levelname = record.levelname
        if levelname in self.COLORS:
            record.levelname = f"{self.COLORS[levelname]}{levelname}{Colors.NC}"
        return super().format(record)

class GitRepoManager:
    """Main Git Repository Manager class"""
    
    VERSION = "2.0.0"
    
    def __init__(self, args):
        self.args = args
        self.config_file = args.file
        self.dry_run = args.dry_run
        self.parallel_jobs = args.parallel
        self.skip_existing = args.skip_existing
        self.force = args.force
        self.interactive = args.interactive
        self.retry_count = args.retry
        self.timeout = args.timeout
        self.include_pattern = args.include
        self.exclude_pattern = args.exclude
        self.use_ssh = args.ssh
        self.submodules = args.submodules
        self.mirror = args.mirror
        self.bare = args.bare
        
        self.remotes: Dict[str, str] = {}
        self.repos: List[RepoConfig] = []
        self.stats = Statistics()
        
        # Setup logging
        self.setup_logging()
        
        # Add SUCCESS level
        logging.SUCCESS = 25
        logging.addLevelName(logging.SUCCESS, 'SUCCESS')
        logging.Logger.success = lambda inst, msg, *args, **kwargs: inst.log(logging.SUCCESS, msg, *args, **kwargs)
        logging.success = lambda msg, *args, **kwargs: logging.log(logging.SUCCESS, msg, *args, **kwargs)
    
    def setup_logging(self):
        """Setup logging configuration"""
        # Console handler
        console_handler = logging.StreamHandler(sys.stderr)
        console_handler.setFormatter(ColoredFormatter(
            '[%(levelname)s] %(message)s'
        ))
        
        # Configure root logger
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.DEBUG if self.args.verbose else logging.INFO)
        self.logger.addHandler(console_handler)
        
        # File handler if log file specified
        if self.args.log:
            file_handler = logging.FileHandler(self.args.log)
            file_handler.setFormatter(logging.Formatter(
                '[%(asctime)s] [%(levelname)s] %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            ))
            self.logger.addHandler(file_handler)
    
    def check_dependencies(self):
        """Check if required dependencies are installed"""
        if not shutil.which('git'):
            self.logger.error("git is not installed. Please install it first.")
            sys.exit(1)
    
    def load_config(self):
        """Load configuration from file"""
        config_path = Path(self.config_file)
        
        if not config_path.exists():
            self.logger.error(f"Config file '{self.config_file}' not found!")
            sys.exit(1)
        
        try:
            # Execute the config file to get variables
            config_globals = {}
            with open(config_path, 'r') as f:
                exec(f.read(), config_globals)
            
            # Load remotes
            self.remotes = config_globals.get('REMOTE', {})
            
            # Load repos
            repos_data = config_globals.get('repos', [])
            for repo_line in repos_data:
                parts = repo_line.split()
                repo = parts[0] if len(parts) > 0 else None
                folder = parts[1] if len(parts) > 1 else None
                branch = parts[2] if len(parts) > 2 else None
                
                if repo:
                    self.repos.append(RepoConfig(repo, folder, branch))
            
            self.stats.total = len(self.repos)
            self.logger.info(f"Loaded {self.stats.total} repositories from config")
            
        except Exception as e:
            self.logger.error(f"Error loading config: {e}")
            sys.exit(1)
    
    def should_process_repo(self, repo: str) -> bool:
        """Check if repository should be processed based on filters"""
        if self.include_pattern and not re.search(self.include_pattern, repo):
            return False
        
        if self.exclude_pattern and re.search(self.exclude_pattern, repo):
            return False
        
        return True
    
    def convert_url(self, url: str) -> str:
        """Convert URL to SSH if needed"""
        if self.use_ssh and url.startswith('https://'):
            # Convert https://github.com/user/repo to git@github.com:user/repo
            parsed = urlparse(url)
            path = parsed.path.lstrip('/')
            return f"git@{parsed.netloc}:{path}"
        return url
    
    def execute_command(self, cmd: List[str], cwd: Optional[str] = None, 
                       retry: bool = True) -> Tuple[bool, str]:
        """Execute command with retry logic"""
        attempts = self.retry_count if retry else 1
        
        for attempt in range(1, attempts + 1):
            if attempt > 1:
                self.logger.warning(f"Retry attempt {attempt}/{attempts}")
                time.sleep(2)
            
            try:
                if self.dry_run:
                    cmd_str = ' '.join(cmd) if isinstance(cmd, list) else cmd
                    self.logger.info(f"DRY RUN: {cmd_str}")
                    return True, ""
                
                result = subprocess.run(
                    cmd,
                    cwd=cwd,
                    capture_output=True,
                    text=True,
                    timeout=self.timeout
                )
                
                if result.returncode == 0:
                    return True, result.stdout
                else:
                    if attempt == attempts:
                        self.logger.debug(f"Command failed: {result.stderr}")
                    continue
                    
            except subprocess.TimeoutExpired:
                self.logger.error(f"Command timed out after {self.timeout} seconds")
                if attempt == attempts:
                    return False, "Timeout"
            except Exception as e:
                self.logger.error(f"Command execution error: {e}")
                if attempt == attempts:
                    return False, str(e)
        
        return False, "Max retries reached"
    
    def clone_repository(self, config: RepoConfig, remote: str, depth: Optional[int], 
                        current: int) -> bool:
        """Clone a single repository"""
        repo = config.repo
        target_folder = config.target_folder
        
        if not self.should_process_repo(repo):
            self.logger.info(f"[{current}/{self.stats.total}] Skipping {repo} (filtered)")
            return False
        
        if self.interactive:
            response = input(f"Clone {repo}? [Y/n] ").strip().lower()
            if response and response != 'y':
                return False
        
        self.logger.info(f"[{current}/{self.stats.total}] Processing {repo}")
        
        # Check if folder exists
        if Path(target_folder).exists():
            if self.skip_existing:
                self.logger.warning(f"Folder '{target_folder}' exists, skipping")
                return False
            elif not self.force:
                self.logger.error(f"Folder '{target_folder}' exists. Use --force or --skip-existing")
                return None  # Return None to indicate failure (not skipped)
            else:
                self.logger.warning(f"Removing existing folder '{target_folder}'")
                if not self.dry_run:
                    shutil.rmtree(target_folder)
        
        # Build clone command
        repo_url = f"{self.remotes.get(remote, remote)}/{repo}"
        repo_url = self.convert_url(repo_url)
        
        cmd = ['git', 'clone']
        
        if depth:
            cmd.extend(['--depth', str(depth)])
        if config.branch:
            cmd.extend(['-b', config.branch])
        if self.submodules:
            cmd.append('--recurse-submodules')
        if self.mirror:
            cmd.append('--mirror')
        if self.bare:
            cmd.append('--bare')
        
        cmd.extend([repo_url, target_folder])
        
        success, output = self.execute_command(cmd)
        
        if success:
            self.logger.success(f"Successfully cloned {repo}")
            return True
        else:
            self.logger.error(f"Failed to clone {repo}")
            return None
    
    def push_repository(self, config: RepoConfig, remote: str, current: int) -> bool:
        """Push a single repository"""
        repo = config.repo
        target_folder = config.target_folder
        
        if not self.should_process_repo(repo):
            return False
        
        if not Path(target_folder).exists():
            self.logger.warning(f"[{current}/{self.stats.total}] Folder '{target_folder}' not found, skipping")
            return False
        
        self.logger.info(f"[{current}/{self.stats.total}] Pushing {repo}")
        
        cmd = ['git', 'push', remote]
        if config.branch:
            cmd.append(config.branch)
        
        success, output = self.execute_command(cmd, cwd=target_folder)
        
        if success:
            self.logger.success(f"Successfully pushed {repo}")
            return True
        else:
            self.logger.error(f"Failed to push {repo}")
            return None
    
    def sync_repository(self, config: RepoConfig, current: int) -> bool:
        """Sync a single repository (pull + push)"""
        repo = config.repo
        target_folder = config.target_folder
        
        if not self.should_process_repo(repo):
            return False
        
        if not Path(target_folder).exists():
            self.logger.warning(f"[{current}/{self.stats.total}] Folder '{target_folder}' not found, skipping")
            return False
        
        self.logger.info(f"[{current}/{self.stats.total}] Syncing {repo}")
        
        # Pull
        pull_success, _ = self.execute_command(
            ['git', 'pull', '--rebase'], 
            cwd=target_folder
        )
        
        if not pull_success:
            self.logger.error(f"Failed to pull {repo}")
            return None
        
        # Push
        push_success, _ = self.execute_command(
            ['git', 'push'], 
            cwd=target_folder
        )
        
        if push_success:
            self.logger.success(f"Successfully synced {repo}")
            return True
        else:
            self.logger.error(f"Failed to push {repo}")
            return None
    
    def process_repos_parallel(self, operation, *args):
        """Process repositories in parallel"""
        with ThreadPoolExecutor(max_workers=self.parallel_jobs) as executor:
            futures = []
            for i, config in enumerate(self.repos, 1):
                future = executor.submit(operation, config, *args, i)
                futures.append(future)
            
            for future in as_completed(futures):
                result = future.result()
                if result is True:
                    self.stats.success += 1
                elif result is False:
                    self.stats.skipped += 1
                else:  # None means failed
                    self.stats.failed += 1
    
    def process_repos_sequential(self, operation, *args):
        """Process repositories sequentially"""
        for i, config in enumerate(self.repos, 1):
            result = operation(config, *args, i)
            if result is True:
                self.stats.success += 1
            elif result is False:
                self.stats.skipped += 1
            else:  # None means failed
                self.stats.failed += 1
    
    def cmd_clone(self):
        """Clone repositories command"""
        self.load_config()
        remote = getattr(self.args, 'remote', 'origin')
        depth = getattr(self.args, 'depth', None)
        
        self.logger.info(f"Starting clone operation for {self.stats.total} repositories")
        
        if self.parallel_jobs > 1:
            self.process_repos_parallel(self.clone_repository, remote, depth)
        else:
            self.process_repos_sequential(self.clone_repository, remote, depth)
        
        self.stats.print_summary(self.logger)
    
    def cmd_push(self):
        """Push repositories command"""
        self.load_config()
        remote = getattr(self.args, 'remote', 'origin')
        
        self.logger.info(f"Starting push operation for {self.stats.total} repositories")
        
        if self.parallel_jobs > 1:
            self.process_repos_parallel(self.push_repository, remote)
        else:
            self.process_repos_sequential(self.push_repository, remote)
        
        self.stats.print_summary(self.logger)
    
    def cmd_sync(self):
        """Sync repositories command"""
        self.load_config()
        
        self.logger.info(f"Starting sync operation for {self.stats.total} repositories")
        
        if self.parallel_jobs > 1:
            self.process_repos_parallel(self.sync_repository)
        else:
            self.process_repos_sequential(self.sync_repository)
        
        self.stats.print_summary(self.logger)
    
    def cmd_status(self):
        """Show status of repositories"""
        self.load_config()
        
        self.logger.info("Repository Status Report\n")
        
        for config in self.repos:
            repo = config.repo
            target_folder = config.target_folder
            
            if not Path(target_folder).exists():
                print(f"{Colors.RED}✗{Colors.NC} {repo} - Not cloned")
                continue
            
            # Get current branch
            success, branch = self.execute_command(
                ['git', 'branch', '--show-current'],
                cwd=target_folder,
                retry=False
            )
            current_branch = branch.strip() if success else 'unknown'
            
            # Check status
            success, status = self.execute_command(
                ['git', 'status', '--porcelain'],
                cwd=target_folder,
                retry=False
            )
            
            # Check ahead/behind
            success, ahead_behind = self.execute_command(
                ['git', 'rev-list', '--left-right', '--count', 'HEAD...@{u}'],
                cwd=target_folder,
                retry=False
            )
            
            if status.strip():
                print(f"{Colors.YELLOW}●{Colors.NC} {repo} - Modified (branch: {current_branch})")
            elif success and ahead_behind.strip():
                behind, ahead = ahead_behind.strip().split()
                if int(behind) > 0 or int(ahead) > 0:
                    print(f"{Colors.YELLOW}↕{Colors.NC} {repo} - Out of sync (↓{behind} ↑{ahead}, branch: {current_branch})")
                else:
                    print(f"{Colors.GREEN}✓{Colors.NC} {repo} - Clean (branch: {current_branch})")
            else:
                print(f"{Colors.GREEN}✓{Colors.NC} {repo} - Clean (branch: {current_branch})")
    
    def cmd_backup(self):
        """Create backup of repositories"""
        self.load_config()
        
        output = getattr(self.args, 'output', 
                        f"repos-backup-{datetime.now().strftime('%Y%m%d-%H%M%S')}.tar.gz")
        
        self.logger.info(f"Creating backup archive: {output}")
        
        # Collect folders to backup
        folders = []
        for config in self.repos:
            if Path(config.target_folder).exists():
                folders.append(config.target_folder)
        
        if not folders:
            self.logger.error("No repositories found to backup")
            return
        
        if self.dry_run:
            self.logger.info(f"DRY RUN: Would backup {len(folders)} repositories to {output}")
            return
        
        try:
            with tarfile.open(output, "w:gz") as tar:
                for folder in folders:
                    self.logger.info(f"Adding {folder} to archive...")
                    tar.add(folder)
            
            self.logger.success(f"Backup created: {output}")
            
            # Get file size
            size_mb = Path(output).stat().st_size / (1024 * 1024)
            self.logger.info(f"Archive size: {size_mb:.2f} MB")
            
        except Exception as e:
            self.logger.error(f"Backup failed: {e}")
    
    def cmd_discover(self):
        """Discover repositories in a folder"""
        scan_dir = getattr(self.args, 'scan_dir', '.')
        output = getattr(self.args, 'output', 'repos-discovered.txt')
        
        self.logger.info(f"Discovering repositories in: {scan_dir}")
        
        repos_found = []
        
        # Find all .git directories
        for root, dirs, files in os.walk(scan_dir):
            if '.git' in dirs:
                repo_dir = Path(root)
                repo_name = repo_dir.name
                
                # Get remote URL
                success, remote_url = self.execute_command(
                    ['git', 'config', '--get', 'remote.origin.url'],
                    cwd=str(repo_dir),
                    retry=False
                )
                
                # Get current branch
                success_branch, branch = self.execute_command(
                    ['git', 'branch', '--show-current'],
                    cwd=str(repo_dir),
                    retry=False
                )
                
                if remote_url:
                    # Extract repo path from URL
                    repo_path = remote_url.strip()
                    # Remove .git suffix and extract path
                    repo_path = re.sub(r'\.git$', '', repo_path)
                    repo_path = re.sub(r'^.*[:/]([^/]+/[^/]+)$', r'\1', repo_path)
                    
                    branch_name = branch.strip() if success_branch else 'main'
                    repos_found.append((repo_path, repo_name, branch_name))
                
                # Don't recurse into .git
                dirs.remove('.git')
        
        # Write config file
        with open(output, 'w') as f:
            f.write("# Auto-generated repository configuration\n")
            f.write(f"# Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            f.write("REMOTE = {\n")
            f.write('    "origin": "https://github.com/username",\n')
            f.write('    "gitlab": "https://gitlab.com/username",\n')
            f.write("}\n\n")
            f.write("repos = [\n")
            
            for repo_path, repo_name, branch in repos_found:
                f.write(f'    "{repo_path} {repo_name} {branch}",\n')
            
            f.write("]\n")
        
        self.logger.success(f"Discovered {len(repos_found)} repositories. Config saved to: {output}")
    
    def cmd_import_github(self):
        """Import repositories from GitHub"""
        username = self.args.username
        include_private = self.args.private
        output = getattr(self.args, 'output', 'repos-github.txt')
        
        self.logger.info(f"Importing repositories from GitHub user/org: {username}")
        
        try:
            import urllib.request
            
            api_url = f"https://api.github.com/users/{username}/repos?per_page=100"
            if include_private:
                api_url = "https://api.github.com/user/repos?per_page=100"
            
            req = urllib.request.Request(api_url)
            req.add_header('Accept', 'application/vnd.github.v3+json')
            
            with urllib.request.urlopen(req) as response:
                repos_data = json.loads(response.read())
            
            # Write config file
            with open(output, 'w') as f:
                f.write(f"# GitHub repositories for {username}\n")
                f.write(f"# Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                f.write("REMOTE = {\n")
                f.write(f'    "origin": "https://github.com/{username}",\n')
                f.write("}\n\n")
                f.write("repos = [\n")
                
                for repo in repos_data:
                    full_name = repo['full_name']
                    repo_name = repo['name']
                    default_branch = repo.get('default_branch', 'main')
                    f.write(f'    "{full_name} {repo_name} {default_branch}",\n')
                
                f.write("]\n")
            
            self.logger.success(f"GitHub import complete. Config saved to: {output}")
            self.logger.info(f"Imported {len(repos_data)} repositories")
            
        except Exception as e:
            self.logger.error(f"GitHub import failed: {e}")
    
    def cmd_list(self):
        """List configured repositories"""
        self.load_config()
        
        print(f"{Colors.BLUE}Configured Repositories:{Colors.NC}\n")
        
        for i, config in enumerate(self.repos, 1):
            exists = "✓" if Path(config.target_folder).exists() else "✗"
            print(f"{i}. {exists} {config.repo}")
            print(f"   Folder: {config.target_folder}")
            print(f"   Branch: {config.branch or 'default'}\n")
        
        print(f"Total: {len(self.repos)} repositories")
    
    def cmd_check(self):
        """Check repository accessibility"""
        self.load_config()
        
        self.logger.info(f"Checking accessibility of {self.stats.total} repositories")
        
        for config in self.repos:
            repo_url = f"{self.remotes.get('origin', '')}/ {config.repo}"
            
            self.logger.info(f"Checking {config.repo}...")
            
            success, _ = self.execute_command(
                ['git', 'ls-remote', repo_url],
                retry=False
            )
            
            if success:
                self.logger.success(f"✓ {config.repo} is accessible")
                self.stats.success += 1
            else:
                self.logger.error(f"✗ {config.repo} is NOT accessible")
                self.stats.failed += 1
        
        self.stats.print_summary(self.logger)
    
    def cmd_init(self):
        """Initialize config template"""
        output = getattr(self.args, 'output', 'repos.txt')
        
        if Path(output).exists() and not self.force:
            self.logger.error(f"Config file '{output}' already exists. Use --force to overwrite.")
            return
        
        template = '''# Git Repository Manager Configuration
# Format: "repository folder branch"

# Define remote URLs
REMOTE = {
    "origin": "https://github.com/username",
    "gitlab": "https://gitlab.com/username",
    "bitbucket": "https://bitbucket.org/username",
}

# Define repositories
repos = [
    "user/repo1 repo1 main",
    "user/repo2 custom-folder develop",
    "user/repo3",
]
'''
        
        with open(output, 'w') as f:
            f.write(template)
        
        self.logger.success(f"Template config created: {output}")
    
    def cmd_add(self):
        """Add repository to config"""
        repo = self.args.repository
        folder = getattr(self.args, 'folder', None)
        branch = getattr(self.args, 'branch', None)
        
        if not Path(self.config_file).exists():
            self.logger.error(f"Config file '{self.config_file}' not found!")
            return
        
        # Read existing config
        with open(self.config_file, 'r') as f:
            content = f.read()
        
        # Build repo line
        repo_line = f'    "{repo}'
        if folder:
            repo_line += f' {folder}'
        if branch:
            repo_line += f' {branch}'
        repo_line += '",\n'
        
        # Add to repos array
        if 'repos = [' in content:
            content = content.replace('repos = [', f'repos = [\n{repo_line}', 1)
        else:
            self.logger.error("Invalid config file format")
            return
        
        # Write back
        with open(self.config_file, 'w') as f:
            f.write(content)
        
        self.logger.success(f"Added {repo} to config")
    
    def cmd_remove(self):
        """Remove repository from config"""
        repo = self.args.repository
        
        if not Path(self.config_file).exists():
            self.logger.error(f"Config file '{self.config_file}' not found!")
            return
        
        # Read existing config
        with open(self.config_file, 'r') as f:
            lines = f.readlines()
        
        # Filter out the repo
        new_lines = []
        removed = False
        for line in lines:
            if f'"{repo}' not in line or 'repos = [' in line:
                new_lines.append(line)
            else:
                removed = True
        
        if not removed:
            self.logger.warning(f"Repository {repo} not found in config")
            return
        
        # Write back
        with open(self.config_file, 'w') as f:
            f.writelines(new_lines)
        
        self.logger.success(f"Removed {repo} from config")
    
    def cmd_validate(self):
        """Validate repositories are in sync"""
        self.load_config()
        
        self.logger.info(f"Validating {self.stats.total} repositories")
        
        for config in self.repos:
            target_folder = config.target_folder
            
            if not Path(target_folder).exists():
                self.logger.warning(f"✗ {config.repo} - Not cloned")
                self.stats.failed += 1
                continue
            
            # Check if clean
            success, status = self.execute_command(
                ['git', 'status', '--porcelain'],
                cwd=target_folder,
                retry=False
            )
            
            if status.strip():
                self.logger.warning(f"● {config.repo} - Has uncommitted changes")
                self.stats.failed += 1
                continue
            
            # Check if synced with remote
            success, _ = self.execute_command(
                ['git', 'fetch'],
                cwd=target_folder,
                retry=False
            )
            
            success, ahead_behind = self.execute_command(
                ['git', 'rev-list', '--left-right', '--count', 'HEAD...@{u}'],
                cwd=target_folder,
                retry=False
            )
            
            if success and ahead_behind.strip():
                behind, ahead = ahead_behind.strip().split()
                if int(behind) > 0 or int(ahead) > 0:
                    self.logger.warning(f"↕ {config.repo} - Out of sync (↓{behind} ↑{ahead})")
                    self.stats.failed += 1
                    continue
            
            self.logger.success(f"✓ {config.repo} - Valid")
            self.stats.success += 1
        
        self.stats.print_summary(self.logger)

def create_parser():
    """Create argument parser"""
    parser = argparse.ArgumentParser(
        description='Git Repository Manager - Advanced multi-repository management tool',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  %(prog)s clone --parallel 5 --skip-existing
  %(prog)s sync --interactive --retry 3
  %(prog)s backup --output backup.tar.gz
  %(prog)s import-github username --private
  %(prog)s discover ~/projects --output repos.txt
        '''
    )
    
    parser.add_argument('-v', '--version', action='version', 
                       version=f'%(prog)s {GitRepoManager.VERSION}')
    
    # Global options
    parser.add_argument('-f', '--file', default='repos.txt',
                       help='Config file (default: repos.txt)')
    parser.add_argument('--log', help='Log to file')
    parser.add_argument('--dry-run', action='store_true',
                       help='Show commands without executing')
    parser.add_argument('--parallel', type=int, default=1,
                       help='Process N repos simultaneously (default: 1)')
    parser.add_argument('--skip-existing', action='store_true',
                       help='Skip if folder already exists')
    parser.add_argument('--force', action='store_true',
                       help='Force overwrite existing folders')
    parser.add_argument('--interactive', action='store_true',
                       help='Prompt before each operation')
    parser.add_argument('--retry', type=int, default=3,
                       help='Retry failed operations N times (default: 3)')
    parser.add_argument('--timeout', type=int, default=300,
                       help='Operation timeout in seconds (default: 300)')
    parser.add_argument('--include', help='Only process repos matching pattern')
    parser.add_argument('--exclude', help='Skip repos matching pattern')
    parser.add_argument('--ssh', action='store_true',
                       help='Use SSH URLs instead of HTTPS')
    parser.add_argument('--submodules', action='store_true',
                       help='Include submodules recursively')
    parser.add_argument('--mirror', action='store_true',
                       help='Create mirror clones')
    parser.add_argument('--bare', action='store_true',
                       help='Create bare repositories')
    parser.add_argument('--verbose', action='store_true',
                       help='Verbose output')
    
    # Subcommands
    subparsers = parser.add_subparsers(dest='command', help='Commands')
    
    # Clone command
    clone_parser = subparsers.add_parser('clone', aliases=['c'],
                                          help='Clone repositories from config file')
    clone_parser.add_argument('-r', '--remote', default='origin',
                             help='Remote name (default: origin)')
    clone_parser.add_argument('-d', '--depth', type=int,
                             help='Shallow clone depth')
    
    # Push command
    push_parser = subparsers.add_parser('push', aliases=['p'],
                                         help='Push repositories to remote')
    push_parser.add_argument('-r', '--remote', default='origin',
                            help='Remote name (default: origin)')
    
    # Sync command
    sync_parser = subparsers.add_parser('sync', aliases=['s'],
                                         help='Sync repositories (pull + push)')
    
    # Status command
    status_parser = subparsers.add_parser('status', aliases=['st'],
                                           help='Show status of all repositories')
    
    # Backup command
    backup_parser = subparsers.add_parser('backup', aliases=['b'],
                                           help='Create backup archive of all repos')
    backup_parser.add_argument('-o', '--output',
                              help='Output file name')
    
    # Discover command
    discover_parser = subparsers.add_parser('discover', aliases=['d'],
                                             help='Discover repos in folder and generate config')
    discover_parser.add_argument('scan_dir', nargs='?', default='.',
                                help='Directory to scan (default: current)')
    discover_parser.add_argument('-o', '--output', default='repos-discovered.txt',
                                help='Output config file')
    
    # Import GitHub command
    github_parser = subparsers.add_parser('import-github',
                                           help='Import repos from GitHub user/org')
    github_parser.add_argument('username', help='GitHub username or organization')
    github_parser.add_argument('--private', action='store_true',
                              help='Include private repositories')
    github_parser.add_argument('-o', '--output', default='repos-github.txt',
                              help='Output config file')
    
    # Import GitLab command
    gitlab_parser = subparsers.add_parser('import-gitlab',
                                           help='Import repos from GitLab user/org')
    gitlab_parser.add_argument('username', help='GitLab username or organization')
    gitlab_parser.add_argument('--private', action='store_true',
                              help='Include private repositories')
    gitlab_parser.add_argument('-o', '--output', default='repos-gitlab.txt',
                              help='Output config file')
    gitlab_parser.add_argument('--url', default='https://gitlab.com',
                              help='GitLab instance URL (default: https://gitlab.com)')
    
    # List command
    list_parser = subparsers.add_parser('list', aliases=['ls'],
                                         help='List all configured repositories')
    
    # Check command
    check_parser = subparsers.add_parser('check',
                                          help='Check accessibility of all repositories')
    
    # Validate command
    validate_parser = subparsers.add_parser('validate', aliases=['v'],
                                             help='Validate repositories are in sync')
    
    # Add command
    add_parser = subparsers.add_parser('add',
                                        help='Add repository to config')
    add_parser.add_argument('repository', help='Repository path (e.g., user/repo)')
    add_parser.add_argument('--folder', help='Local folder name')
    add_parser.add_argument('--branch', help='Branch name')
    
    # Remove command
    remove_parser = subparsers.add_parser('remove', aliases=['rm'],
                                           help='Remove repository from config')
    remove_parser.add_argument('repository', help='Repository path to remove')
    
    # Init command
    init_parser = subparsers.add_parser('init',
                                         help='Create template config file')
    init_parser.add_argument('-o', '--output', default='repos.txt',
                            help='Output config file')
    
    return parser

def main():
    """Main entry point"""
    parser = create_parser()
    args = parser.parse_args()
    
    # Show help if no command specified
    if not args.command:
        parser.print_help()
        sys.exit(0)
    
    # Create manager instance
    manager = GitRepoManager(args)
    manager.check_dependencies()
    
    # Execute command
    command_map = {
        'clone': manager.cmd_clone,
        'c': manager.cmd_clone,
        'push': manager.cmd_push,
        'p': manager.cmd_push,
        'sync': manager.cmd_sync,
        's': manager.cmd_sync,
        'status': manager.cmd_status,
        'st': manager.cmd_status,
        'backup': manager.cmd_backup,
        'b': manager.cmd_backup,
        'discover': manager.cmd_discover,
        'd': manager.cmd_discover,
        'import-github': manager.cmd_import_github,
        'import-gitlab': lambda: manager.logger.error("GitLab import not yet implemented"),
        'list': manager.cmd_list,
        'ls': manager.cmd_list,
        'check': manager.cmd_check,
        'validate': manager.cmd_validate,
        'v': manager.cmd_validate,
        'add': manager.cmd_add,
        'remove': manager.cmd_remove,
        'rm': manager.cmd_remove,
        'init': manager.cmd_init,
    }
    
    command_func = command_map.get(args.command)
    if command_func:
        try:
            command_func()
        except KeyboardInterrupt:
            manager.logger.warning("\nOperation cancelled by user")
            sys.exit(130)
        except Exception as e:
            manager.logger.error(f"Unexpected error: {e}")
            if args.verbose:
                import traceback
                traceback.print_exc()
            sys.exit(1)
    else:
        manager.logger.error(f"Unknown command: {args.command}")
        sys.exit(1)

if __name__ == '__main__':
    main()