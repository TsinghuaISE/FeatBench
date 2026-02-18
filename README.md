# FeatBench

Offical implementation of our paper "FeatBench: Towards More Realistic Evaluation of Feature-level Code Generation". [paper](https://arxiv.org/abs/2509.22237)

![paper](assets/paper.png)

## Abstract
Evaluating Large Language Models (LLMs) on repository-level feature implementation is a critical frontier in software engineering. However, establishing a benchmark that faithfully mirrors realistic development scenarios remains a significant challenge. Existing feature-level benchmarks generally suffer from two primary limitations: unrealistic task inputs enriched with code hints and significant data leakage risks due to their static nature. To address these limitations, we propose a new benchmark – FeatBench, which introduces the following advances: ❶ Realistic Task Inputs. Task inputs consist solely of natural language requirements, strictly devoid of code hints (e.g., function signatures). This format mirrors realistic software development by requiring agents to independently bridge the gap between abstract user intent and concrete code changes. ❷ Evolving Data. FeatBench employs a fully automated pipeline to construct new benchmark versions from the latest repositories, effectively mitigating data contamination. The initial release comprises 157 tasks sourced from 27 actively maintained repositories. We evaluate two state-of-the-art agent frameworks with four leading LLMs on FeatBench. The results reveal that FeatBench poses a significant challenge, with the highest resolved rate reaching only 29.94%. Crucially, our analysis uncovers a prevalent behavioral pattern of aggressive implementation, which leads to "scope creep" and widespread regressions where agents break existing features by diverging from the user’s explicit intent. We release FeatBench, our automated pipeline, and all experimental results to facilitate further community research.

## Benchmark Highlights

- **Realistic Task Inputs** – task inputs consist solely of natural language requirements (e.g., ``I want to...''), imposing a substantial challenge that requires agents to independently comprehend the repository context and devise a strategy to implement the feature without explicit hints.
- **Release-grounded corpus** – each instance originates from a curated GitHub release and pull-request history, yielding high-signal requirements and verified reference patches.
- **Rigorous, evolving pipeline** – a multi-stage, fully automated collection system applies quality filters, mitigates data contamination, and can roll forward continuously as new releases ship.
- **Comprehensive regression checks** – Fail-to-Pass (F2P) and Pass-to-Pass (P2P) pytest selections ensure both new behaviour and legacy functionality are validated.
- **Diverse domains** – 27 actively maintained repositories spanning AI/ML, DevOps, web platforms, and productivity tools provide broad coverage of real-world tech stacks.

## Metadata

![metadata](assets/metadata.png)

The FeatBench benchmark contains the following key attributes for each evaluation instance:

- **repo**: Repository name in the format `owner/name` (e.g., "home-assistant/core")
- **instance_id**: Unique identifier combining repository name and issue/PR number (e.g., "home-assistant__core-153575")
- **org**: GitHub organization or user name
- **number**: Associated issue or pull request number
- **version**: Version tag of the release containing this feature
- **base_commit**: Git commit hash of the base version before the feature implementation
- **created_at**: Timestamp when the feature was released (ISO 8601 format)
- **patch**: Array of source code modifications
  - **filename**: Path to the modified file
  - **status**: Modification status (typically "modified")
  - **additions**: Number of lines added
  - **deletions**: Number of lines deleted
  - **changes**: Total number of changes (additions + deletions)
  - **patch**: Unified diff format showing the actual code changes
- **test_patch**: Array of test file modifications with the same structure as `patch`
  - Contains additions, deletions, and unified diffs for test files
  - Used to validate both FAIL_TO_PASS and PASS_TO_PASS test cases
- **problem_statement**: Human-readable description of the feature to implement
- **test_files**: List of test file paths that validate this feature
- **processed**: Boolean flag indicating whether the instance has been validated
- **FAIL_TO_PASS**: Tests that should pass after implementing the feature
- **PASS_TO_PASS**: Tests that should continue passing (regression checks)
- **docker_image**: Named like `featbench_<repo>:<id>`

### Example Instance Structure
```json
{
  "repo": "home-assistant/core",
  "instance_id": "home-assistant__core-153575",
  "base_commit": "3f9421ab0801a339e62506c0c123066c53810efb",
  "patch": [...],
  "test_patch": [...],
  "problem_statement": "I want to ensure that when my Z-Wave adapter...",
  "created_at": "2025-10-03T16:39:14Z",
  "version": "2025.10.1",
  "org": "home-assistant",
  "number": 153575,
  "test_files": ["tests/components/zwave_js/test_config_flow.py"],
  "processed": true
}
```

## Prerequisites
- System python with `uv` (used to install `trae-agent`).
- Python 3.10 or later (3.13 recommended to match the configured containers).
- Docker Engine 24+.
- Recent Git installation for repository cloning inside containers.
- Access tokens:
  - A GitHub personal access token with `repo` and `read:org` permissions.
  - An LLM provider key (OpenAI-compatible) for PR summarisation.

## Installation
```bash
git clone https://github.com/Kndy666/FeatBench.git
cd FeatBench

conda create -n FeatBench python=3.13 -y
conda activate FeatBench

pip install -r requirements.txt
pip install -e .
```

## Instructions

FeatBench operates in three main stages: **Data Curation**, **Environment Configuration**, and **Evaluation**. Each stage has its own configuration and requirements.

### Stage 1: Data Curation Pipeline

The data curation system mines real feature releases from GitHub to generate evaluation benchmarks.

The process includes four phases:
1. **Repository Collection** (`release_collector.py`): Mines GitHub for repositories based on stars and release count
2. **Release Analysis** (`release_analyzer.py`): Analyzes release content to identify new features
3. **PR Enhancement** (`pr_analyzer.py`): Enriches with PR-level diffs and LLM-generated task descriptions
4. **Output Generation** (`main.py`): Orchestrates all phases to produce `final_analysis_results.json`

#### 1. Configure Sensitive Information

First, create a `.secrets.toml` file in the `docker_agent` and configure the following:

```bash
# data_collect/.secrets.toml
[common]
github_token = "ghp_xxx"  # GitHub Personal Access Token with 'repo' and 'read:org' permissions
openai_api_key = "xxx"  # OpenAI-compatible API key
```

#### 2. Modify Data Collection Configuration

Modify the settings in `data_collect/config.toml` as needed.

#### 3. Run Data Collection

```bash
cd FeatBench
python -m data_collect.main
```
The script supports several optional command-line arguments to customize the execution:
- `--no-cache`: Do not use cached data; reprocess all repositories and analyses from scratch.
- `--collect-only`: Perform only the repository collection phase and skip subsequent release analysis and PR enhancement.
- `--analyze-only`: Perform only the release analysis phase, assuming repository collection has already been done.
- `--enhance-only`: Perform only the PR enhancement phase, assuming previous phases are complete.

### Phase 2: Environment Configuration Pipeline

Build Docker container environments to prepare evaluation infrastructure.

#### 1. Temporary File Directory

The program stores temporary files in the `docker_agent/swap/` subdirectory under the running directory:
- Contains `trae-agent` clones and configuration files
- Creates independent container images for each repository
- **Note**: First run may require several GB of space, depending on the number of repositories processed

#### 2. Trae-Agent Configuration

On the first run, the program will clone trae-agent in the `docker_agent/swap/trae-agent/` directory and exit.

You need to configure in the `trae-agent` directory:

```bash
cd docker_agent/swap/trae-agent
cp trae_config.yaml.example trae_config.yaml
# Edit trae_config.yaml as needed
```

#### 3. Modify Settings (if needed)

Modify configurations in `docker_agent/settings.toml` as needed:

- **Logging configuration** (`level`, `log_file`): Adjust log level and output location
- **Execution configuration** (`max_specs_per_repo`): Limit maximum specifications per repository
- **Docker configuration** (`docker_timeout`): Container operation timeout (default: 180 seconds)
- **Proxy configuration** (`proxy_enabled`, `proxy_http`, `proxy_https`): If operating in a proxy environment

#### 4. Run Environment Building

```bash
cd FeatBench
python -m docker_agent.runner.main --agents your_agent
```

### Phase 3: Evaluation Execution

Run agents in isolated Docker containers to implement features.

#### 1. Dataset Transformation
First, transform the data from the collection phase:

```bash
cd FeatBench
python -m docker_agent.tools.main
```

**Alternatively, you can use the preprocessed dataset file `dataset/featbench_v1_0.json` (156 curated instances used in the original paper).**

#### 2. Pulling prebuilt Docker images (if needed)

If you don't want to build all images locally, you can pull the prebuilt FeatBench container images that we uploaded to GitHub Container Registry (GHCR). These images have the short names used by the project (e.g., `featbench_<repo>:<id>`).

```bash
# Pull images referenced in dataset/featbench_v1_0.json (default)
python scripts/pull_images.py --dataset dataset/featbench_v1_0.json

# Pull images with 8 parallel downloads (faster when bandwidth allows)
python scripts/pull_images.py --dataset dataset/featbench_v1_0.json --concurrency 8

# Dry-run: only show what would be pulled (no network activity)
python scripts/pull_images.py --dataset dataset/featbench_v1_0.json --dry-run
```

#### 3. Trae-Agent Evaluation (Default)

The codebase defaults to supporting trae-agent evaluation. 

Then run the evaluator:

```bash
python -m docker_agent.runner.main --evaluate --agents your_agent
```

#### 4. Custom Agent Evaluation (if needed)

To evaluate other agents or models, follow these three steps:

**Step 1**: Create a new file in the `docker_agent/agents/` directory, inheriting from the `BaseAgent` class in `base.py`

```python
# docker_agent/agents/your_agent.py
from docker_agent.agents.base import BaseAgent

class YourAgent(BaseAgent):
    def _prepare_agent_code(self):
        # Prepare agent code
        pass

    def prepare_resources(self, patch: str) -> Optional[List[Dict[str, Any]]]:
        # Prepare agent-specific resources before evaluation
        pass
	def evaluate(self, spec: Spec, operator, *args, **kwargs) -> Dict[str, Any]:
		# Evaluate agent on a specific spec
		pass
```

Refer to `docker_agent/agents/trae_agent.py` for detailed implementation.

**Step 2**: Modify the `_create_agent` method in `docker_agent/agents/manager.py`

```python
def _create_agent(self, agent_name: str, config: dict) -> BaseAgent:
    if agent_name == "trae_agent":
        return TraeAgent(config)
    elif agent_name == "your_agent":
        return YourAgent(config)
    else:
        ...
```

**Step 3**: Update the `docker_agent/agents.toml` configuration file

```toml
# docker_agent/agents.toml
[your_agent]
name = "Your Agent"
model = "gpt-4"
provider = "openai"
install_commands = [
    "pip install your-agent-package"
]
repo_url = "https://github.com/your/agent"
branch = "main"
```

### Output Files

The evaluation process generates the following key files:

- `final_analysis_results*.json`: Curated evaluation summaries
- `evaluation_results_file.json`: Agents Evaluation results
- `docker_agent/swap/`: Temporary working directory (can be safely deleted)

### Output Format

Each evaluation instance produces a result object with the following structure:

```json
{
  "agent": "trae-agent",
  "model": "deepseek-chat",
  "instance_id": "instructlab__instructlab-3286",
  "success_f2p": false,
  "success_p2p": false,
  "success": false,
  "passed_f2p_tests": [],
  "passed_p2p_tests": [],
  "total_tokens": 542776,
  "patch_application": {
    "total_files_num": 1,
    "applied_files_num": 1,
    "applied_files": [
      "dspy/primitives/tool.py"
    ],
    "patch_content": "diff --git a/dspy/primitives/tool.py ..."
  }
}
```

- **agent**: Name of the evaluated agent (e.g., "trae-agent", "your_agent")
- **model**: Underlying LLM model used by the agent
- **instance_id**: Unique identifier matching the input instance
- **success_f2p**: Whether all FAIL_TO_PASS tests pass
- **success_p2p**: Whether all PASS_TO_PASS tests pass
- **success**: Overall success (true if both F2P and P2P succeed)
- **passed_f2p_tests**: List of FAIL_TO_PASS tests that passed
- **passed_p2p_tests**: List of PASS_TO_PASS tests that passed
- **total_tokens**: Total tokens consumed during the evaluation
- **patch_application**: Details about the generated patch
  - **total_files_num**: Total number of files in the patch
  - **applied_files_num**: Number of files successfully applied
  - **applied_files**: List of files that were successfully applied
  - **patch_content**: Unified diff of the generated changes

## Leaderboard

![paper](assets/board.png)

## License

This project is licensed under the [MIT License](LICENSE).

## Citation

If you use FeatBench in your research, please cite our paper:

```bibtex
@misc{chen2025featbenchevaluatingcodingagents,
      title={FeatBench: Evaluating Coding Agents on Feature Implementation for Vibe Coding}, 
      author={Haorui Chen and Chengze Li and Jia Li},
      year={2025},
      eprint={2509.22237},
      archivePrefix={arXiv},
      primaryClass={cs.CL},
      url={https://arxiv.org/abs/2509.22237}, 
}
```

## Support

If you have any questions or suggestions, please email us at `hrchen@std.uestc.edu.cn` or feel free to make issues~