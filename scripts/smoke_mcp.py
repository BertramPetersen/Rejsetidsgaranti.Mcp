"""Exercise real stdio transport and all six tools using synthetic data only."""

import asyncio
import os
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def run() -> None:
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "dsb_claims_mcp.server"],
        env={**os.environ, "DSB_MCP_PROVIDER": "demo"},
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = (await session.list_tools()).tools
            names = {tool.name for tool in tools}
            expected = {
                "dsb_status",
                "dsb_list_tickets",
                "dsb_list_journeys",
                "dsb_get_delay_evidence",
                "dsb_prepare_claim_form",
                "dsb_get_form_handoff",
            }
            assert names == expected, names
            for tool in tools:
                assert tool.annotations.readOnlyHint is True
            for name in sorted(names):
                args = {}
                if name == "dsb_get_delay_evidence":
                    args = {"journey_id": "demo-journey-1"}
                if name in {"dsb_prepare_claim_form", "dsb_get_form_handoff"}:
                    args = {"ticket_id": "demo-ticket-1"}
                result = await session.call_tool(name, args)
                assert not result.isError, (name, result)
                assert result.structuredContent is not None, name
                if name == "dsb_prepare_claim_form":
                    assert result.structuredContent["fields"]["actual_arrival"].endswith("+02:00")
                    assert result.structuredContent["submitted"] is False
                    assert result.structuredContent["form_filled"] is False
            invalid = await session.call_tool("dsb_prepare_claim_form", {"ticket_id": "missing"})
            assert invalid.structuredContent["ok"] is False
            elicitation = await session.call_tool(
                "dsb_prepare_claim_form", {"ticket_id": "demo-ticket-unassigned"}
            )
            assert elicitation.structuredContent["status"] == "needs_input"
            details = {
                "origin": "København H",
                "destination": "Odense",
                "scheduled_departure": "2026-10-01T10:00:00+02:00",
                "scheduled_arrival": "2026-10-01T11:30:00+02:00",
                "actual_arrival": "2026-10-01T12:15:00+02:00",
            }
            filled = await session.call_tool(
                "dsb_prepare_claim_form",
                {
                    "ticket_id": "demo-ticket-unassigned",
                    "journey_details": details,
                },
            )
            assert not filled.isError, filled
            assert filled.structuredContent["journey_source"] == "user_supplied"
    print("PASS: stdio initialize, six tools, annotations, errors, and user-supplied journey flow")


if __name__ == "__main__":
    asyncio.run(run())
