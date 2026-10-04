import sys
from pathlib import Path

# Make repo-root modules (tools, main.py helpers) importable under pytest.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Hermetic test suite: the runtime .env may point SKILLS_REGISTRY at the live
# S3-compatible bucket, and main.py's load_dotenv(override=True) beats process
# env — so, like the summarizer/compressor factories in test_main_integration,
# pin the skill registry factory to local-directory mode for the whole suite.
# The registry's own S3 integration tests live in nm-skills-registry.
import nm_memory_layer.skills as _skills
from nm_skills_registry import LocalDirStore, SkillRegistry as _SkillRegistry

_skills.registry_from_env = lambda skills_dir="skills", **_: _SkillRegistry(
    LocalDirStore(skills_dir), ""
)
