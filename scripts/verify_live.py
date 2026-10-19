"""Exercise installed Ollama with explicitly hand-drawn sample visuals."""

from backend.integrations import storyboard
from backend.media import probe, render
from backend.models import Export, Project, Settings
from backend.store import asset_path, put
from scripts.sample import create

create()
settings = Settings(model="llama3.2:1b")
project = storyboard(
    Project(
        id="ollama-verified",
        prompt="A short inspiring film about sunrise and a fresh start. Two short scenes.",
        duration=10,
    ),
    settings,
)
for index, scene in enumerate(project.scenes):
    scene.asset = f"sample-landscape-{index % 2}.png"
project.description += " Visuals are hand-drawn test artwork, not AI-generated."
output = render(
    project,
    Export(width=360, height=640, font_size=28, transition="crossfade", fade=0.5),
    settings,
    lambda stage, pct: print(stage, flush=True),
    lambda: False,
)
project.exports.append(output)
put("project", project.id, project.model_dump())
put("settings", "local", settings.model_dump())
print("VERIFIED", project.title, probe(asset_path(output["asset"])), output["asset"], flush=True)
