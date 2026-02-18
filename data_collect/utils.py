import re
import time
import requests
import base64
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, asdict

from .config import (
    GITHUB_API_BASE, GITHUB_HEADERS,
    TEST_DIRECTORIES, TEST_FILE_PATTERNS
)

@dataclass
class FileChange:
    """Represents file change information"""
    filename: str
    status: str  # 'added', 'removed', 'modified', 'renamed'
    additions: int
    deletions: int
    changes: int
    patch: Optional[str] = None  # diff content

    def to_dict(self) -> Dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict) -> 'FileChange':
        return cls(**data)

@dataclass
class Commit:
    """Represents a Git commit"""
    sha: str
    message: str
    date: str
    author: str

    def to_dict(self) -> Dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict) -> 'Commit':
        return cls(**data)

@dataclass
class Release:
    """Represents a release version"""
    tag_name: str
    name: str
    body: str
    published_at: str
    target_commitish: str
    version_tuple: Tuple[int, ...]
    version_key: str
    
    def to_dict(self) -> Dict:
        data = asdict(self)
        return data
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'Release':
        release = cls(**data)
        return release

@dataclass
class Repository:
    """Represents a repository and its release information"""
    full_name: str
    stargazers_count: int
    size: int
    topics: List[str]
    releases_count: int
    major_releases: List[Release]
    readme_content: str
    ci_configs: Dict[str, str]
    processed_at: str
    
    def to_dict(self) -> Dict:
        data = asdict(self)
        data['major_releases'] = [release.to_dict() for release in self.major_releases]
        return data
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'Repository':
        repo = cls(**data)
        repo.major_releases = [Release.from_dict(release_data) for release_data in data.get("major_releases", [])]
        return repo

def is_test_file(file_path: str) -> bool:
    """Check if file is a test file"""
    # Check if path contains test directory
    path_parts = file_path.lower().split('/')

    # First check if path contains a test directory
    has_test_dir = any(part in TEST_DIRECTORIES for part in path_parts)
    if not has_test_dir:
        return False

    # Check if filename matches test file patterns
    file_name = Path(file_path).name

    return any(re.match(pattern, file_name) for pattern in TEST_FILE_PATTERNS)

def extract_version_components(tag_name):
    """
    Extract version number components from tag name.
    Supports various formats like: v1.2.3, 1.2.3, 1-2-3, release-1.2.3, version.1.2.3, etc.
    Handles possible spaces in version numbers, like "v 1.2.3" or "1. 2. 3"
    Supports any number of version components (e.g., 1.2.3.4.5.6)

    Returns:
    - If version number successfully extracted, returns a version tuple (major, minor, patch, ...)
    - If unable to extract, returns None
    """
    # First clean input string, remove leading/trailing spaces
    tag_name = tag_name.strip()

    # Helper function to extract version components from a string
    def extract_from_string(s):
        # This pattern captures all version components in a flexible way
        version_pattern = re.compile(r'(\d+)(?:\s*[.\-_]\s*\d+)*')

        match = version_pattern.search(s)
        if match:
            version_numbers = re.findall(r'\d+', match.group())
            return tuple(int(v) for v in version_numbers)
        return None

    # 1. First try direct version pattern matching from string start
    version_tuple = extract_from_string(tag_name)
    if version_tuple:
        return version_tuple

    # 2. If no match at start, try removing common prefixes then matching
    version_string = tag_name
    common_prefixes = ['version', 'release', 'ver', 'rel', 'v']  # Sorted by length, match longer first

    for prefix in common_prefixes:
        # Use regex for more precise prefix matching
        prefix_pattern = re.compile(rf'^{re.escape(prefix)}[.\-_\s]*', re.IGNORECASE)
        if prefix_pattern.match(tag_name):
            version_string = prefix_pattern.sub('', tag_name).strip()
            version_tuple = extract_from_string(version_string)
            if version_tuple:
                return version_tuple
            break

    return None

# =========================
# GitHub API Functions
# =========================

def extract_pr_number_from_url(pr_url: str) -> Optional[str]:
    """Extract PR number from PR URL"""
    match = re.search(r'/pull/(\d+)', pr_url)
    return match.group(1) if match else None

def get_pr_info(repo_name: str, pr_number: str) -> Optional[Dict]:
    """Get PR basic information"""
    url = f"{GITHUB_API_BASE}/repos/{repo_name}/pulls/{pr_number}"

    try:
        time.sleep(0.5)  # Rate limit
        response = requests.get(url, headers=GITHUB_HEADERS)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"⚠️ Failed to get PR#{pr_number} info: {response.status_code}")
            return None
    except Exception as e:
        print(f"⚠️ Exception getting PR#{pr_number} info: {e}")
        return None

def get_pr_files(repo_name: str, pr_number: str) -> List[FileChange]:
    """Get PR file change information as FileChange objects"""
    url = f"{GITHUB_API_BASE}/repos/{repo_name}/pulls/{pr_number}/files"

    try:
        time.sleep(0.5)  # Rate limit
        response = requests.get(url, headers=GITHUB_HEADERS)
        if response.status_code == 200:
            files_data = response.json()
            file_changes = []

            for file_data in files_data:
                file_change = FileChange(
                    filename=file_data.get('filename', ''),
                    status=file_data.get('status', ''),
                    additions=file_data.get('additions', 0),
                    deletions=file_data.get('deletions', 0),
                    changes=file_data.get('changes', 0),
                    patch=file_data.get('patch', '')
                )
                file_changes.append(file_change)

            return file_changes
        else:
            print(f"⚠️ Failed to get PR#{pr_number} files: {response.status_code}")
            return []
    except Exception as e:
        print(f"⚠️ Exception getting PR#{pr_number} files: {e}")
        return []

def get_file_content(repo_name: str, file_path: str, ref: str) -> Optional[str]:
    """Get file content at a specific commit"""
    url = f"{GITHUB_API_BASE}/repos/{repo_name}/contents/{file_path}?ref={ref}"

    try:
        time.sleep(0.5)  # Rate limit
        response = requests.get(url, headers=GITHUB_HEADERS)
        if response.status_code == 200:
            data = response.json()
            # GitHub API returns base64 encoded content
            if 'content' in data:
                content = data['content']
                # Remove any whitespace
                content = content.strip()
                # Decode base64
                decoded_content = base64.b64decode(content).decode('utf-8')
                return decoded_content
            return None
        else:
            print(f"⚠️ Failed to get file {file_path} at {ref}: {response.status_code}")
            return None
    except Exception as e:
        print(f"⚠️ Exception getting file {file_path}: {e}")
        return None

def get_commit_info(repo_name: str, commit_sha: str) -> Optional[Commit]:
    """Get commit information as Commit object"""
    url = f"{GITHUB_API_BASE}/repos/{repo_name}/commits/{commit_sha}"

    try:
        time.sleep(0.5)  # Rate limit
        response = requests.get(url, headers=GITHUB_HEADERS)
        if response.status_code == 200:
            commit_data = response.json()
            return Commit(
                sha=commit_data.get('sha', ''),
                message=commit_data.get('commit', {}).get('message', ''),
                date=commit_data.get('commit', {}).get('author', {}).get('date', ''),
                author=commit_data.get('commit', {}).get('author', {}).get('name', '')
            )
        else:
            print(f"⚠️ Failed to get commit {commit_sha}: {response.status_code}")
            return None
    except Exception as e:
        print(f"⚠️ Exception getting commit {commit_sha}: {e}")
        return None

def get_candidate_repos(min_stars: int, rank_start: int, rank_end: int) -> List[Dict]:
    """Get Python repositories within specified ranking range from GitHub API as candidate pool."""
    print(f"Getting Python repositories with Stars >= {min_stars}, filtering ranking {rank_start}-{rank_end}...")

    API_URL = "https://api.github.com/search/repositories"
    PARAMS = {
        'q': f'language:python stars:>={min_stars}',
        'sort': 'stars',
        'order': 'desc',
        'per_page': 100  # GitHub API max 100 per request
    }

    all_repos = []
    page = 1
    current_repo_count = 0

    try:
        while True:
            params_with_page = PARAMS.copy()
            params_with_page['page'] = page

            response = requests.get(API_URL, params=params_with_page, headers=GITHUB_HEADERS)
            response.raise_for_status()

            data = response.json()
            repos = data.get('items', [])

            if not repos:  # No more results
                break

            # Check ranking range for current page
            page_start_rank = current_repo_count + 1
            page_end_rank = current_repo_count + len(repos)

            print(f"✅ Retrieved page {page}, repository ranking {page_start_rank}-{page_end_rank}")

            # If starting rank of current page exceeds target end rank, stop fetching
            if page_start_rank > rank_end:
                print(f"Exceeded target ranking range {rank_end}, stopping fetch")
                break

            # Filter repositories within target ranking range
            for i, repo in enumerate(repos):
                repo_rank = current_repo_count + i + 1
                if rank_start <= repo_rank <= rank_end:
                    repo['rank'] = repo_rank  # Add ranking info
                    all_repos.append(repo)

            current_repo_count += len(repos)

            # If all repositories in target ranking range have been fetched, stop
            if page_end_rank >= rank_end:
                print(f"Retrieved target ranking range {rank_end}, stopping fetch")
                break

            # GitHub search API returns max 1000 results with pagination limit
            if current_repo_count >= data.get('total_count', 0) or page >= 10:
                break

            page += 1
            time.sleep(0.5)  # Avoid API limit

        print(f"✅ Total retrieved {len(all_repos)} repositories within ranking range {rank_start}-{rank_end}")
        return all_repos

    except requests.exceptions.HTTPError as e:
        print(f"HTTP Error: {e}")
        if e.response.status_code == 403:
            print("API rate limit exceeded. Please use Token or wait and retry.")
        return []

def get_repository_info(repo_name: str) -> Optional[Dict]:
    """Get detailed information for single repository"""
    try:
        repo_url = f"{GITHUB_API_BASE}/repos/{repo_name}"
        time.sleep(0.5)  # Rate limit
        response = requests.get(repo_url, headers=GITHUB_HEADERS)
        response.raise_for_status()

        repo_data = response.json()

        # Return data in same format as get_candidate_repos
        return {
            'full_name': repo_data['full_name'],
            'stargazers_count': repo_data['stargazers_count'],
            'size': repo_data['size'],
            'topics': repo_data.get('topics', []),
            'language': repo_data.get('language', ''),
            'archived': repo_data.get('archived', False),
            'disabled': repo_data.get('disabled', False),
            'fork': repo_data.get('fork', False),
        }

    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 404:
            print(f"  ⚠️ Repository does not exist: {repo_name}")
        else:
            print(f"  ⚠️ Failed to get repository info: {repo_name} - {e}")
        return None
    except Exception as e:
        print(f"  ⚠️ Exception getting repository info: {repo_name} - {e}")
        return None

def has_test_cases(repo_full_name: str, test_directories: List[str], test_file_patterns: List[str]) -> bool:
    """Check if repository contains test cases"""
    print(f"  > Checking if {repo_full_name} has test cases...")

    try:
        # 1. Check for test directories
        contents_url = f"{GITHUB_API_BASE}/repos/{repo_full_name}/contents"
        time.sleep(0.5)
        response = requests.get(contents_url, headers=GITHUB_HEADERS)
        response.raise_for_status()

        contents = response.json()

        # Check root directory for test-related directories
        has_test_directory = False
        test_directories_found = []
        for item in contents:
            if item.get('type') == 'dir':
                dir_name = item.get('name', '').lower()
                if any(test_dir in dir_name for test_dir in test_directories):
                    print(f"  > ✅ Found test directory: {item.get('name')}")
                    has_test_directory = True
                    test_directories_found.append(item.get('name'))

        # 2. Check root directory for test files
        for item in contents:
            if item.get('type') == 'file':
                file_name = item.get('name', '')
                if any(re.match(pattern, file_name) for pattern in test_file_patterns):
                    print(f"  > ✅ Found test file: {file_name}")
                    return True

        # 3. Only if test directories found in root, recursively check test directory contents
        if has_test_directory:
            def check_directory_for_tests(repo_name, directory_path):
                """Recursively check if directory contains Python test files"""
                try:
                    dir_url = f"{GITHUB_API_BASE}/repos/{repo_name}/contents/{directory_path}"
                    time.sleep(0.5)
                    response = requests.get(dir_url, headers=GITHUB_HEADERS)
                    if response.status_code == 200:
                        contents = response.json()
                        if isinstance(contents, list):
                            # Check all files in directory at once
                            files = [item for item in contents if item.get('type') == 'file']
                            for item in files:
                                file_name = item.get('name', '')
                                # Check if Python file or test file
                                if file_name.endswith('.py') or any(re.match(pattern, file_name) for pattern in test_file_patterns):
                                    print(f"  > ✅ Found Python file in test directory {directory_path}: {file_name}")
                                    return True

                            # Then recursively check subdirectories
                            directories = [item for item in contents if item.get('type') == 'dir']
                            for dir_item in directories:
                                sub_dir_path = f"{directory_path}/{dir_item.get('name')}"
                                if check_directory_for_tests(repo_name, sub_dir_path):
                                    return True
                    return False
                except Exception as e:
                    print(f"  > ⚠️ Error checking directory {directory_path}: {e}")
                    return False

            # Recursively check each found test directory
            for test_dir in test_directories_found:
                if check_directory_for_tests(repo_full_name, test_dir):
                    return True

        print(f"  > ❌ No obvious test cases found")
        return False

    except requests.exceptions.HTTPError as e:
        print(f"  > ⚠️ Error checking test cases: {e}")
        return False
    except Exception as e:
        print(f"  > ⚠️ Exception checking test cases: {e}")
        return False

def get_repository_readme(repo_full_name: str) -> str:
    """Get repository README content"""
    print(f"  > Getting README for {repo_full_name}...")

    try:
        # Get all files in repository root directory
        root_url = f"{GITHUB_API_BASE}/repos/{repo_full_name}/contents"
        time.sleep(0.5)  # Avoid API limit
        response = requests.get(root_url, headers=GITHUB_HEADERS)
        response.raise_for_status()

        contents = response.json()

        # Common README filename patterns
        readme_patterns = [r'^readme\.md$', r'^readme\.rst$', r'^readme\.txt$', r'^readme$']

        # Check locally if file list contains README
        for item in contents:
            if item.get('type') == 'file':
                file_name = item.get('name', '').lower()
                if any(re.match(pattern, file_name, re.IGNORECASE) for pattern in readme_patterns):
                    # Found README file, get content
                    download_url = item.get('download_url')
                    if download_url:
                        content_response = requests.get(download_url, headers=GITHUB_HEADERS)
                        content_response.raise_for_status()
                        readme_content = content_response.text
                        print(f"  > ✅ Successfully got README ({item.get('name')}), length: {len(readme_content)} characters")
                        return readme_content

        print(f"  > ❌ README file not found")
        return ""

    except Exception as e:
        print(f"  > ⚠️ Error getting README: {e}")
        return ""

def get_ci_configs(repo_full_name: str) -> Dict[str, str]:
    """Get list of CI/CD configuration files and download links for repository"""
    print(f"  > Getting CI/CD configuration file list for {repo_full_name}...")

    ci_configs = {}

    try:
        # Check if .github/workflows directory exists
        workflows_url = f"{GITHUB_API_BASE}/repos/{repo_full_name}/contents/.github/workflows"
        time.sleep(0.5)  # Avoid API limit
        response = requests.get(workflows_url, headers=GITHUB_HEADERS)

        # If directory exists, collect all YAML files info
        if response.status_code == 200:
            contents = response.json()

            for item in contents:
                if item.get('type') == 'file' and (item.get('name', '').endswith('.yml') or item.get('name', '').endswith('.yaml')):
                    file_name = item.get('name', '')
                    file_path = f".github/workflows/{file_name}"
                    download_url = item.get('download_url', '')

                    if download_url:
                        ci_configs[file_path] = download_url
                        print(f"  > ✅ Found CI config: {file_path}")

        if ci_configs:
            print(f"  > ✅ Found {len(ci_configs)} CI configuration files total")
        else:
            print(f"  > ❌ No CI configuration files found")

        return ci_configs

    except Exception as e:
        print(f"  > ⚠️ Error getting CI config list: {e}")
        return {}

def get_repository_releases(repo_full_name: str) -> List[Dict]:
    """Get all releases for a repository from GitHub API"""
    releases_url = f"{GITHUB_API_BASE}/repos/{repo_full_name}/releases"
    try:
        time.sleep(0.5)  # Rate limit
        response = requests.get(releases_url, headers=GITHUB_HEADERS)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 403:
            print(f"\nAPI rate limit exceeded")
            raise
        print(f"  ⚠️ Failed to get releases for {repo_full_name}: {e.response.status_code}")
        return []
    except Exception as e:
        print(f"  ⚠️ Exception getting releases for {repo_full_name}: {e}")
        return []
