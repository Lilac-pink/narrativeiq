import pytest
from models.module1_models import PipelineInput, Episode


@pytest.fixture
def sample_input():
    return PipelineInput(
        story_idea="A radio operator picks up a signal from a station closed 30 years ago.",
        series_title="The Forgotten Signal",
        target_episodes=5
    )


@pytest.fixture
def sample_episode():
    return Episode(
        episode_number=1,
        title="Dead Air",
        plot_beat="Maya Chen picks up a mysterious signal at midnight.",
        characters=["Maya Chen"],
        locations=["Radio Tower 7"]
    )


@pytest.fixture
def mock_episodes():
    return [
        Episode(
            episode_number=1,
            title="Dead Air",
            plot_beat="Maya picks up the signal at midnight.",
            characters=["Maya Chen"],
            locations=["Radio Tower 7"]
        ),
        Episode(
            episode_number=2,
            title="Interference",
            plot_beat="Maya traces the signal to a sealed bunker.",
            characters=["Maya Chen", "Dr. Reeves"],
            locations=["Bunker Entrance"]
        ),
        Episode(
            episode_number=3,
            title="Static",
            plot_beat="Maya discovers encrypted files inside the bunker.",
            characters=["Maya Chen", "Director Osei"],
            locations=["Bunker Interior"]
        ),
    ]
