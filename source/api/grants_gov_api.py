"""
Grants.gov API Client
"""
#%% Import modules and libraries
# First-party libraries
from datetime import datetime, timedelta
import json

# Third-party libraries
from dataclasses import dataclass, asdict
import logging
import requests
from typing import Dict, List, Optional, Any

# Custom modules


#%% Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


#%%
@dataclass
class GrantOpportunity:
    """Represents a grant opportunity from Grants.gov"""
    id: str
    number: str
    title: str
    agency_code: str
    agency_name: str
    open_date: str
    close_date: str
    opp_status: str
    doc_type: str
    aln_list: List[str]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return asdict(self)
    
    @classmethod
    def from_api_response(cls, data: Dict[str, Any]) -> 'GrantOpportunity':
        """Create GrantOpportunity from API response"""
        return cls(
            id=data.get('id', ''),
            number=data.get('number', ''),
            title=data.get('title', ''),
            agency_code=data.get('agencyCode', ''),
            agency_name=data.get('agencyName', ''),
            open_date=data.get('openDate', ''),
            close_date=data.get('closeDate', ''),
            opp_status=data.get('oppStatus', ''),
            doc_type=data.get('docType', ''),
            aln_list=data.get('alnist', [])
        )


class GrantsGovAPIClient:
    """Client for interacting with Grants.gov RESTful API"""
    
    BASE_URL = "https://api.grants.gov/v1/api"
    STAGING_URL = "https://api.staging.grants.gov/v1/api"
    
    def __init__(self, use_staging: bool = False):
        """
        Initialize the API client
        
        Args:
            use_staging: If True, use staging environment instead of production
        """
        self.base_url = self.STAGING_URL if use_staging else self.BASE_URL
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json',
            'User-Agent': 'TFG-Grant-Automation/1.0'
        })
    
    def search_opportunities(
        self,
        keyword: Optional[str] = None,
        opp_num: Optional[str] = None,
        agencies: Optional[str] = None,
        opp_statuses: Optional[str] = "forecasted|posted",
        eligibilities: Optional[str] = None,
        funding_categories: Optional[str] = None,
        aln: Optional[str] = None,
        rows: int = 25,
        start_record_num: int = 0,
        sort_by: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Search for grant opportunities
        
        Args:
            keyword: Search term for opportunity title/description
            opp_num: Specific opportunity number
            agencies: Agency codes (e.g., "HHS", "ED")
            opp_statuses: Status filters - "forecasted|posted|closed|archived"
            eligibilities: Eligibility codes
            funding_categories: Category codes (e.g., "HL" for Health)
            aln: Assistance Listing Number
            rows: Number of results to return (default 25)
            start_record_num: Starting record for pagination
            sort_by: Sort order for results
            
        Returns:
            Dictionary containing search results and metadata
        """
        endpoint = f"{self.base_url}/search2"
        
        # Build request body - only include non-None parameters
        payload = {
            "rows": rows,
            "startRecordNum": start_record_num
        }
        
        if keyword:
            payload["keyword"] = keyword
        if opp_num:
            payload["oppNum"] = opp_num
        if agencies:
            payload["agencies"] = agencies
        if opp_statuses:
            payload["oppStatuses"] = opp_statuses
        if eligibilities:
            payload["eligibilities"] = eligibilities
        if funding_categories:
            payload["fundingCategories"] = funding_categories
        if aln:
            payload["aln"] = aln
        if sort_by:
            payload["sortBy"] = sort_by
        
        logger.info(f"Searching opportunities with params: {payload}")
        
        try:
            response = self.session.post(endpoint, json=payload)
            response.raise_for_status()
            
            data = response.json()
            
            # Check for API errors
            if data.get('errorcode', 0) != 0:
                logger.error(f"API returned error: {data.get('msg')}")
                raise Exception(f"API Error: {data.get('msg')}")
            
            logger.info(f"Found {data['data']['hitCount']} opportunities")
            return data
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed: {str(e)}")
            raise
    
    def get_opportunities(
        self,
        keyword: Optional[str] = None,
        opp_statuses: Optional[str] = "forecasted|posted",
        **kwargs
    ) -> List[GrantOpportunity]:
        """
        Get list of GrantOpportunity objects
        
        Returns parsed list of opportunities ready for processing
        """
        response = self.search_opportunities(
            keyword=keyword,
            opp_statuses=opp_statuses,
            **kwargs
        )
        
        opportunities = []
        for opp_data in response['data'].get('oppHits', []):
            opportunities.append(GrantOpportunity.from_api_response(opp_data))
        
        return opportunities
    
    def get_new_opportunities(
        self,
        days_back: int = 1,
        opp_statuses: str = "forecasted|posted",
        **kwargs
    ) -> List[GrantOpportunity]:
        """
        Get opportunities posted in the last N days
        
        This is useful for daily monitoring automation.
        Note: Grants.gov doesn't have a native date filter in search2,
        so we filter by open date after retrieval.
        
        Args:
            days_back: Number of days to look back (default 1 for daily runs)
            opp_statuses: Status filters
            **kwargs: Additional search parameters
            
        Returns:
            List of new opportunities
        """
        logger.info(f"Fetching opportunities from last {days_back} days")
        
        # Get all recent opportunities (we'll filter by date)
        all_opps = self.get_opportunities(
            opp_statuses=opp_statuses,
            rows=100,  # Get more to ensure we catch all new ones
            **kwargs
        )
        
        # Calculate cutoff date
        cutoff_date = datetime.now() - timedelta(days=days_back)
        
        # Filter by open date
        new_opps = []
        for opp in all_opps:
            try:
                # Parse date (format: MM/DD/YYYY)
                if opp.open_date:
                    opp_date = datetime.strptime(opp.open_date, '%m/%d/%Y')
                    if opp_date >= cutoff_date:
                        new_opps.append(opp)
            except (ValueError, AttributeError) as e:
                logger.warning(f"Could not parse date for opp {opp.number}: {e}")
                # Include it to be safe
                new_opps.append(opp)
        
        logger.info(f"Found {len(new_opps)} new opportunities")
        return new_opps
    
    def fetch_opportunity_detail(self, opp_id: str) -> Dict[str, Any]:
        """
        Fetch detailed information for a specific opportunity
        
        Note: This uses the fetchOpportunity endpoint which will be
        implemented once we have the full documentation.
        
        Args:
            opp_id: Opportunity ID or number
            
        Returns:
            Detailed opportunity information
        """
        endpoint = f"{self.base_url}/fetchOpportunity"
        
        payload = {"oppId": opp_id}
        
        logger.info(f"Fetching details for opportunity: {opp_id}")
        
        try:
            response = self.session.post(endpoint, json=payload)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to fetch opportunity details: {str(e)}")
            raise


# Example usage
if __name__ == "__main__":
    # Initialize client
    client = GrantsGovAPIClient(use_staging=False)
    
    # Example 1: Search for health-related grants
    print("\n=== Searching for health grants ===")
    results = client.search_opportunities(
        keyword="health",
        opp_statuses="posted",
        rows=5
    )
    print(f"Found {results['data']['hitCount']} total health grants")
    
    # Example 2: Get structured opportunity objects
    print("\n=== Getting opportunity objects ===")
    opportunities = client.get_opportunities(
        keyword="education",
        rows=3
    )
    for opp in opportunities:
        print(f"\n{opp.title}")
        print(f"  Agency: {opp.agency_name}")
        print(f"  Number: {opp.number}")
        print(f"  Status: {opp.opp_status}")
        print(f"  Open: {opp.open_date} | Close: {opp.close_date}")
    
    # Example 3: Get new opportunities from last day (for daily automation)
    print("\n=== New opportunities (last 24 hours) ===")
    new_opps = client.get_new_opportunities(days_back=1)
    print(f"Found {len(new_opps)} new opportunities")