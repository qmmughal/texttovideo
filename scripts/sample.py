"""Create clearly labeled, hand-drawn sample assets; no AI generation is simulated."""

from PIL import Image, ImageDraw

from backend.models import Project, Scene
from backend.store import asset_path, put

SCENES = [
    ("#dbc9a7", "#5f7867", "Every story starts with a little light.", "zoom_in"),
    ("#b7ccd0", "#49665c", "Find a different perspective.", "pan_right"),
]


def create():
    scenes = []
    for i, (background, hill, text, motion) in enumerate(SCENES):
        name = f"sample-landscape-{i}.png"
        image = Image.new("RGB", (960, 1280), background)
        draw = ImageDraw.Draw(image)
        draw.ellipse((380, 180, 680, 480), fill="#f0d99f")
        draw.polygon([(0, 900), (350, 450), (960, 1150), (960, 1280), (0, 1280)], fill=hill)
        draw.polygon([(0, 1100), (720, 600), (960, 850), (960, 1280), (0, 1280)], fill="#304e43")
        image.save(asset_path(name))
        scenes.append(
            Scene(
                id=f"sample-scene-{i}",
                text=text,
                prompt="A cinematic landscape at sunrise",
                duration=5,
                asset=name,
                motion=motion,
            )
        )
    project = Project(
        id="sample",
        title="A different perspective",
        description="Hand-drawn sample artwork for testing the editor and FFmpeg. These are not AI-generated visuals.",
        prompt="A short film about finding inspiration in nature.",
        duration=10,
        scenes=scenes,
    )
    put("project", project.id, project.model_dump())
    print("Created sample project: A different perspective")


if __name__ == "__main__":
    create()
