from types import SimpleNamespace

from release_operator import AutomationRequest, ReleaseLedger, run_automation


def request() -> AutomationRequest:
    return AutomationRequest(
        service="warehouse-loader",
        commit_sha="8f32a12",
        target="staging",
        instruction="Build, publish, and report the release state.",
    )


def test_release_is_blocked_until_build_succeeds() -> None:
    ledger = ReleaseLedger(request())

    blocked = ledger.execute("publish_release", {"detail": "staging release"})
    ledger.execute("record_build", {"status": "succeeded", "detail": "tests passed"})
    published = ledger.execute("publish_release", {"detail": "staging release"})

    assert blocked["status"] == "blocked"
    assert published == {
        "kind": "release",
        "status": "published",
        "detail": "staging release",
    }


class FakeCompletions:
    def __init__(self) -> None:
        self.responses = iter(
            [
                SimpleNamespace(
                    choices=[
                        SimpleNamespace(
                            message=SimpleNamespace(
                                content=None,
                                tool_calls=[
                                    SimpleNamespace(
                                        id="call_build",
                                        function=SimpleNamespace(
                                            name="record_build",
                                            arguments='{"status":"succeeded","detail":"checks passed"}',
                                        ),
                                    ),
                                    SimpleNamespace(
                                        id="call_publish",
                                        function=SimpleNamespace(
                                            name="publish_release",
                                            arguments='{"detail":"deployed to staging"}',
                                        ),
                                    ),
                                ],
                            )
                        )
                    ]
                ),
                SimpleNamespace(
                    choices=[
                        SimpleNamespace(
                            message=SimpleNamespace(
                                content="Build succeeded; staging release published.",
                                tool_calls=None,
                            )
                        )
                    ]
                ),
            ]
        )

    def create(self, **kwargs: object) -> object:
        return next(self.responses)


def test_tool_loop_returns_observable_release_events() -> None:
    fake_client = SimpleNamespace(
        chat=SimpleNamespace(completions=FakeCompletions())
    )

    result = run_automation(request(), client=fake_client)

    assert [event.status for event in result.events] == ["succeeded", "published"]
    assert result.summary == "Build succeeded; staging release published."
