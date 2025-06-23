from typing import Dict, List, Optional


class OpenAlexQueryBuilder:
    """Utility class for building OpenAlex API queries."""

    @staticmethod
    def build_search_query(
        title: str, author: Optional[str] = None, year: Optional[str] = None
    ) -> List[str]:
        """
        Build a list of search queries in order of preference.

        Args:
            title: The title to search for
            author: Optional first author last name
            year: Optional publication year

        Returns:
            List of query strings to try in order
        """
        title_cleaned = title.replace("{", "").replace("}", "").strip() if title else ""
        author_cleaned = (
            author.replace("{", "").replace("}", "").strip() if author else ""
        )
        year_cleaned = year.strip() if year else ""

        if not title_cleaned:
            return []

        queries_to_try = []

        # First priority: all components if available
        if title_cleaned and author_cleaned and year_cleaned:
            queries_to_try.append(f"{title_cleaned} {author_cleaned} {year_cleaned}")
        elif title_cleaned and year_cleaned:
            queries_to_try.append(f"{title_cleaned} {year_cleaned}")

        # Second priority: title + author (no year)
        if title_cleaned and author_cleaned:
            query_with_author = f"{title_cleaned} {author_cleaned}"
            if query_with_author not in queries_to_try:
                queries_to_try.append(query_with_author)

        # Third priority: title only
        if title_cleaned and title_cleaned not in queries_to_try:
            queries_to_try.append(title_cleaned)

        return queries_to_try

    @staticmethod
    def build_search_params(
        query: str, per_page: int = 50, email: Optional[str] = None
    ) -> Dict[str, str]:
        """
        Build search parameters for OpenAlex works API.

        Args:
            query: The search query string
            per_page: Number of results per page (default: 50, max for OpenAlex)
            email: Optional email for polite pool access

        Returns:
            Dictionary of query parameters
        """
        params = {
            "search": query,
            "per_page": str(per_page),
        }

        if email:
            params["mailto"] = email

        return params

    @staticmethod
    def build_doi_filter_params(
        dois: List[str], email: Optional[str] = None
    ) -> Dict[str, str]:
        """
        Build parameters for DOI-based filtering.

        Args:
            dois: List of DOI strings to filter by
            email: Optional email for polite pool access

        Returns:
            Dictionary of query parameters
        """
        # Preprocess DOIs to ensure proper format
        processed_dois = []
        for doi in dois:
            if doi:
                if not doi.startswith("http"):
                    doi = f"https://doi.org/{doi}"
                processed_dois.append(doi)

        piped = "|".join(processed_dois)
        params = {
            "filter": f"doi:{piped}",
            "per_page": str(min(len(processed_dois), 50)),  # API max is 50
        }

        if email:
            params["mailto"] = email

        return params

    @staticmethod
    def build_work_detail_params(email: Optional[str] = None) -> Dict[str, str]:
        """
        Build parameters for fetching individual work details.

        Args:
            email: Optional email for polite pool access

        Returns:
            Dictionary of query parameters
        """
        params = {}

        if email:
            params["mailto"] = email

        return params


# Convenience functions for backward compatibility
def build_search_queries(
    title: str, author: Optional[str] = None, year: Optional[str] = None
) -> List[str]:
    """Build search queries for a bibliographic entry."""
    return OpenAlexQueryBuilder.build_search_query(title, author, year)


def build_search_params(
    query: str, per_page: int = 50, email: Optional[str] = None
) -> Dict[str, str]:
    """Build search parameters for OpenAlex API."""
    return OpenAlexQueryBuilder.build_search_params(query, per_page, email)


def build_doi_params(dois: List[str], email: Optional[str] = None) -> Dict[str, str]:
    """Build DOI filter parameters for OpenAlex API."""
    return OpenAlexQueryBuilder.build_doi_filter_params(dois, email)
