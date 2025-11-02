from mwp_common.workflow_contracts import (
    COMMAND_ORDER_CREATE,
    EVENT_ORDER_CREATED,
    WORKFLOW_COMMANDS_STREAM,
    WORKFLOW_EVENTS_STREAM,
    command_fields,
    event_fields,
)


def test_command_fields_include_required_trace_values() -> None:
    fields = command_fields(
        message_type=COMMAND_ORDER_CREATE,
        workflow_id="workflow-test",
        correlation_id="correlation-test",
        user_id="user-local-001",
    )

    assert fields["message_type"] == COMMAND_ORDER_CREATE
    assert fields["workflow_id"] == "workflow-test"
    assert fields["correlation_id"] == "correlation-test"
    assert fields["message_version"] == "1"
    assert fields["producer"] == "workflow-service"
    assert fields["command_id"] == fields["message_id"]
    assert WORKFLOW_COMMANDS_STREAM == "project.workflow.commands"


def test_event_fields_include_required_trace_values() -> None:
    fields = event_fields(
        message_type=EVENT_ORDER_CREATED,
        workflow_id="workflow-test",
        correlation_id="correlation-test",
        order_id="order-test",
    )

    assert fields["message_type"] == EVENT_ORDER_CREATED
    assert fields["workflow_id"] == "workflow-test"
    assert fields["event_id"] == fields["message_id"]
    assert WORKFLOW_EVENTS_STREAM == "project.workflow.events"
