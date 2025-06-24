import asyncio
import os
from typing import Dict, List, Optional

from google.api_core import exceptions as google_exceptions
from google.analytics.admin import AnalyticsAdminServiceClient
from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import (
    DateRange,
    Dimension,
    Metric,
    RunReportRequest,
    RunRealtimeReportRequest,
    GetMetadataRequest,
)
from mcp.server.fastmcp import FastMCP

# --- MCP Server Initialization ---
mcp = FastMCP(
    "Google Analytics 4 Server",
    host="0.0.0.0",
    port=8002,
    title="Google Analytics 4 Server",
    description="A server for interacting with Google Analytics 4 Data API.",
)

# --- Google Analytics Client ---
# Note: Google Application Credentials must be configured for this to work.
# Run `gcloud auth application-default login` before starting the container.
# The docker-compose.yaml file is configured to mount the credentials.

class GA4Client:
    def __init__(self):
        try:
            quota_project_id = os.getenv("GOOGLE_CLOUD_PROJECT")
            client_options = {"quota_project_id": quota_project_id} if quota_project_id else {}
            
            self.admin_client = AnalyticsAdminServiceClient(client_options=client_options)
            self.data_client = BetaAnalyticsDataClient(client_options=client_options)
        except Exception as e:
            raise RuntimeError(f"Failed to initialize Google Analytics clients. "
                               f"Please ensure you have authenticated via 'gcloud auth application-default login'. Error: {e}")

    def list_accounts(self) -> List[Dict]:
        try:
            results = self.admin_client.list_account_summaries()
            accounts = []
            for summary in results:
                if summary.property_summaries:
                    for prop_summary in summary.property_summaries:
                        accounts.append(
                            {
                                "display_name": f"{summary.display_name} - {prop_summary.display_name}",
                                "property_id": prop_summary.property.split("/")[-1],
                            }
                        )
            if not accounts:
                raise google_exceptions.NotFound("No Google Analytics accounts were found for your user. Please check your permissions.")
            return accounts
        except google_exceptions.PermissionDenied as e:
            error_message = (
                "Permission Denied: Could not list Google Analytics accounts. "
                "Please ensure the 'Analytics Admin API' is enabled for your project ('lukaskostka') "
                "and that your user has the necessary permissions. "
                f"Original error: {e.message}"
            )
            raise google_exceptions.PermissionDenied(error_message) from e
        except google_exceptions.GoogleAPICallError as e:
            raise google_exceptions.GoogleAPICallError(f"A Google API error occurred while listing accounts: {e.message}") from e
        except Exception as e:
            raise google_exceptions.GoogleAPICallError(f"An unexpected error occurred while listing accounts: {str(e)}") from e

    def run_report(self, property_id: str, metrics: List[str], dimensions: Optional[List[str]] = None, date_ranges: Optional[List[Dict[str, str]]] = None) -> Dict:
        if not property_id:
            raise google_exceptions.InvalidArgument("property_id must be provided.")
        request = RunReportRequest(
            property=f"properties/{property_id}",
            metrics=[Metric(name=metric) for metric in metrics],
            dimensions=[Dimension(name=dim) for dim in dimensions] if dimensions else [],
            date_ranges=[DateRange(**dr) for dr in date_ranges] if date_ranges else [],
        )
        response = self.data_client.run_report(request)
        return self._format_report_response(response)
    
    def run_realtime_report(self, property_id: str, metrics: List[str], dimensions: Optional[List[str]] = None) -> Dict:
        if not property_id:
            raise google_exceptions.InvalidArgument("property_id must be provided.")
        request = RunRealtimeReportRequest(
            property=f"properties/{property_id}",
            metrics=[Metric(name=metric) for metric in metrics],
            dimensions=[Dimension(name=dim) for dim in dimensions] if dimensions else [],
        )
        response = self.data_client.run_realtime_report(request)
        return self._format_report_response(response)

    def get_metadata(self, property_id: str) -> Dict:
        if not property_id:
            raise google_exceptions.InvalidArgument("property_id must be provided.")
        request = GetMetadataRequest(name=f"properties/{property_id}/metadata")
        response = self.data_client.get_metadata(request)
        return {
            "metrics": [m.api_name for m in response.metrics],
            "dimensions": [d.api_name for d in response.dimensions],
        }

    def _format_report_response(self, response) -> Dict:
        headers = [header.name for header in response.dimension_headers] + [
            header.name for header in response.metric_headers
        ]
        rows = []
        for row in response.rows:
            row_data = [item.value for item in row.dimension_values] + [
                item.value for item in row.metric_values
            ]
            rows.append(dict(zip(headers, row_data)))
        return {"headers": headers, "rows": rows}


ga4_client = GA4Client()

# --- Tools ---

@mcp.tool()
async def list_ga_accounts() -> List[Dict]:
    """Lists all available Google Analytics accounts and their properties."""
    return await asyncio.to_thread(ga4_client.list_accounts)

@mcp.tool()
async def run_ga_report(property_id: str, metrics: List[str], dimensions: Optional[List[str]] = None, date_ranges: Optional[List[Dict[str, str]]] = None) -> Dict:
    """Runs a standard GA4 report with customizable metrics, dimensions, and date ranges."""
    return await asyncio.to_thread(ga4_client.run_report, property_id, metrics, dimensions, date_ranges)

@mcp.tool()
async def run_ga_realtime_report(property_id: str, metrics: List[str], dimensions: Optional[List[str]] = None) -> Dict:
    """Gets real-time data for the past 30 minutes."""
    return await asyncio.to_thread(ga4_client.run_realtime_report, property_id, metrics, dimensions)

@mcp.tool()
async def get_ga_metadata(property_id: str) -> Dict:
    """Retrieves available metrics and dimensions for a GA4 property."""
    return await asyncio.to_thread(ga4_client.get_metadata, property_id)

# --- Main Execution ---
if __name__ == "__main__":
    print("Starting Google Analytics 4 MCP server on port 8002...")
    print("Connect to this server using http://localhost:8002/sse")
    mcp.run(transport="sse") 