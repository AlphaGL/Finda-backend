# ai_chatbot/services/web_search.py
import asyncio
import aiohttp
import logging
from typing import Dict, List, Any, Optional, Tuple
from urllib.parse import urlencode, urlparse, quote_plus
import json
import re
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
import requests
from django.core.cache import cache
from django.conf import settings

logger = logging.getLogger(__name__)


class WebSearchService:
    """
    Advanced web search service for finding external products
    Supports multiple search engines and e-commerce sites
    """
    
    def __init__(self):
        self.cache_timeout = 3600  # 1 hour
        self.max_results_per_source = 10
        self.request_timeout = 30
        self.max_concurrent_requests = 5
        
        # Search engines and APIs
        self.search_engines = {
            'google': {
                'enabled': True,
                'base_url': 'https://www.googleapis.com/customsearch/v1',
                'api_key': getattr(settings, 'GOOGLE_SEARCH_API_KEY', None),
                'cse_id': getattr(settings, 'GOOGLE_CSE_ID', None),
            },
            'bing': {
                'enabled': True,
                'base_url': 'https://api.bing.microsoft.com/v7.0/search',
                'api_key': getattr(settings, 'BING_SEARCH_API_KEY', None),
            },
            'serp': {
                'enabled': False,  # Enable if you have SerpAPI key
                'base_url': 'https://serpapi.com/search.json',
                'api_key': getattr(settings, 'SERPAPI_KEY', None),
            }
        }
        
        # E-commerce sites to search
        self.ecommerce_sites = {
            'amazon': {
                'enabled': True,
                'domains': ['amazon.com', 'amazon.co.uk', 'amazon.de', 'amazon.fr'],
                'search_path': '/s',
                'search_param': 'k',
                'selectors': {
                    'title': '[data-component-type="s-search-result"] h2 a span',
                    'price': '.a-price-whole',
                    'image': '.s-image',
                    'rating': '.a-icon-alt'
                }
            },
            'ebay': {
                'enabled': True,
                'domains': ['ebay.com', 'ebay.co.uk', 'ebay.de'],
                'search_path': '/sch/i.html',
                'search_param': '_nkw',
                'selectors': {
                    'title': '.s-item__title',
                    'price': '.s-item__price',
                    'image': '.s-item__image img',
                    'shipping': '.s-item__shipping'
                }
            },
            'aliexpress': {
                'enabled': True,
                'domains': ['aliexpress.com'],
                'search_path': '/wholesale',
                'search_param': 'SearchText',
                'selectors': {
                    'title': '._18_85 a',
                    'price': '._12A8D',
                    'image': '.images img'
                }
            },
            'jumia': {
                'enabled': True,
                'domains': ['jumia.com.ng', 'jumia.co.ke', 'jumia.com.eg'],
                'search_path': '/catalog/',
                'search_param': 'q',
                'selectors': {
                    'title': '.name',
                    'price': '.prc',
                    'image': '.img img'
                }
            }
        }
        
        # Headers for web scraping
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
        }
    
    async def search_products(
        self, 
        query: str, 
        search_keywords: List[str] = None,
        location_context: Dict = None,
        max_results: int = 20
    ) -> Dict[str, Any]:
        """
        Main method to search for products across multiple sources
        
        Args:
            query: Original search query
            search_keywords: List of optimized search keywords from Gemini
            location_context: User's location for localized results
            max_results: Maximum number of results to return
            
        Returns:
            Dict containing search results from all sources
        """
        try:
            # Check cache first
            cache_key = self._generate_cache_key(query, search_keywords, location_context)
            cached_results = cache.get(cache_key)
            if cached_results:
                logger.info(f"Returning cached web search results for: {query}")
                return cached_results
            
            start_time = datetime.now()
            
            # Prepare search terms
            search_terms = search_keywords or [query]
            
            # Initialize results structure
            results = {
                'query': query,
                'search_terms_used': search_terms,
                'products': [],
                'total_found': 0,
                'sources': {},
                'search_metadata': {
                    'search_duration': 0,
                    'sources_searched': 0,
                    'successful_sources': 0,
                    'failed_sources': 0,
                    'location_context': location_context
                },
                'timestamp': datetime.now().isoformat(),
                'success': True
            }
            
            # Create tasks for concurrent searching
            search_tasks = []
            
            # Search using search engines (Google, Bing)
            for engine_name, engine_config in self.search_engines.items():
                if engine_config['enabled'] and engine_config.get('api_key'):
                    for search_term in search_terms[:3]:  # Limit to 3 terms per engine
                        task = self._search_with_engine(engine_name, search_term, location_context)
                        search_tasks.append((f"{engine_name}_{search_term}", task))
            
            # Search e-commerce sites directly
            for site_name, site_config in self.ecommerce_sites.items():
                if site_config['enabled']:
                    for search_term in search_terms[:2]:  # Limit to 2 terms per site
                        task = self._search_ecommerce_site(site_name, search_term, location_context)
                        search_tasks.append((f"{site_name}_{search_term}", task))
            
            # Execute searches concurrently
            if search_tasks:
                # Limit concurrent requests
                semaphore = asyncio.Semaphore(self.max_concurrent_requests)
                limited_tasks = [
                    self._run_with_semaphore(semaphore, task[1]) 
                    for task in search_tasks[:15]  # Limit total tasks
                ]
                
                task_results = await asyncio.gather(*limited_tasks, return_exceptions=True)
                
                # Process results
                for i, (task_name, task) in enumerate(search_tasks[:15]):
                    if i < len(task_results):
                        task_result = task_results[i]
                        source_name = task_name.split('_')[0]
                        
                        results['search_metadata']['sources_searched'] += 1
                        
                        if isinstance(task_result, Exception):
                            logger.error(f"Error in {task_name}: {str(task_result)}")
                            results['search_metadata']['failed_sources'] += 1
                            if source_name not in results['sources']:
                                results['sources'][source_name] = {
                                    'success': False,
                                    'error': str(task_result),
                                    'results_count': 0
                                }
                        elif task_result and task_result.get('success'):
                            results['search_metadata']['successful_sources'] += 1
                            source_results = task_result.get('products', [])
                            
                            # Add source information to each product
                            for product in source_results:
                                product['search_source'] = source_name
                                product['search_term'] = task_name.split('_', 1)[1]
                            
                            results['products'].extend(source_results)
                            
                            # Update source info
                            if source_name not in results['sources']:
                                results['sources'][source_name] = {
                                    'success': True,
                                    'results_count': 0,
                                    'search_terms': []
                                }
                            
                            results['sources'][source_name]['results_count'] += len(source_results)
                            if task_name.split('_', 1)[1] not in results['sources'][source_name]['search_terms']:
                                results['sources'][source_name]['search_terms'].append(task_name.split('_', 1)[1])
            
            # Deduplicate and rank results
            results['products'] = self._deduplicate_and_rank_products(results['products'])
            results['products'] = results['products'][:max_results]
            results['total_found'] = len(results['products'])
            
            # Calculate search duration
            end_time = datetime.now()
            results['search_metadata']['search_duration'] = (end_time - start_time).total_seconds()
            
            # Verify and enhance product links
            if results['products']:
                await self._verify_and_enhance_links(results['products'])
            
            # Cache results
            cache.set(cache_key, results, self.cache_timeout)
            
            logger.info(f"Web search completed: {results['total_found']} products found in {results['search_metadata']['search_duration']:.2f}s")
            
            return results
        
        except Exception as e:
            logger.error(f"Error in web product search: {str(e)}")
            return {
                'query': query,
                'products': [],
                'total_found': 0,
                'error': str(e),
                'success': False,
                'timestamp': datetime.now().isoformat()
            }
    
    async def _search_with_engine(
        self, 
        engine_name: str, 
        query: str, 
        location_context: Dict = None
    ) -> Dict[str, Any]:
        """Search using search engine APIs"""
        try:
            engine_config = self.search_engines[engine_name]
            
            if engine_name == 'google':
                return await self._search_google(query, location_context, engine_config)
            elif engine_name == 'bing':
                return await self._search_bing(query, location_context, engine_config)
            elif engine_name == 'serp':
                return await self._search_serpapi(query, location_context, engine_config)
            
            return {'success': False, 'error': 'Unsupported search engine'}
            
        except Exception as e:
            logger.error(f"Error searching with {engine_name}: {str(e)}")
            return {'success': False, 'error': str(e), 'products': []}
    
    async def _search_google(self, query: str, location_context: Dict, config: Dict) -> Dict[str, Any]:
        """Search using Google Custom Search API"""
        try:
            if not config.get('api_key') or not config.get('cse_id'):
                return {'success': False, 'error': 'Google API key or CSE ID not configured'}
            
            # Build search query for shopping
            search_query = f"{query} buy online shop price"
            
            params = {
                'key': config['api_key'],
                'cx': config['cse_id'],
                'q': search_query,
                'num': 10,
                'safe': 'active',
                'searchType': 'image',  # Can help find product images
            }
            
            # Add location context if available
            if location_context and location_context.get('country'):
                params['gl'] = location_context['country'].lower()
            
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.request_timeout)) as session:
                url = f"{config['base_url']}?{urlencode(params)}"
                
                async with session.get(url, headers=self.headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        products = self._parse_google_results(data)
                        
                        return {
                            'success': True,
                            'products': products,
                            'source': 'google',
                            'results_count': len(products)
                        }
                    else:
                        error_text = await response.text()
                        return {'success': False, 'error': f'Google API error: {response.status} - {error_text}'}
        
        except Exception as e:
            logger.error(f"Google search error: {str(e)}")
            return {'success': False, 'error': str(e), 'products': []}
    
    async def _search_bing(self, query: str, location_context: Dict, config: Dict) -> Dict[str, Any]:
        """Search using Bing Search API"""
        try:
            if not config.get('api_key'):
                return {'success': False, 'error': 'Bing API key not configured'}
            
            search_query = f"{query} buy online shop price"
            
            params = {
                'q': search_query,
                'count': 10,
                'offset': 0,
                'mkt': 'en-US',
                'safeSearch': 'Moderate',
            }
            
            # Add location context
            if location_context and location_context.get('country'):
                country_code = location_context['country'].upper()
                if country_code == 'NG':
                    params['mkt'] = 'en-NG'
                elif country_code == 'GB':
                    params['mkt'] = 'en-GB'
            
            headers = {
                **self.headers,
                'Ocp-Apim-Subscription-Key': config['api_key']
            }
            
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.request_timeout)) as session:
                url = f"{config['base_url']}?{urlencode(params)}"
                
                async with session.get(url, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        products = self._parse_bing_results(data)
                        
                        return {
                            'success': True,
                            'products': products,
                            'source': 'bing',
                            'results_count': len(products)
                        }
                    else:
                        error_text = await response.text()
                        return {'success': False, 'error': f'Bing API error: {response.status} - {error_text}'}
        
        except Exception as e:
            logger.error(f"Bing search error: {str(e)}")
            return {'success': False, 'error': str(e), 'products': []}
    
    async def _search_ecommerce_site(
        self, 
        site_name: str, 
        query: str, 
        location_context: Dict = None
    ) -> Dict[str, Any]:
        """Search directly on e-commerce sites"""
        try:
            site_config = self.ecommerce_sites[site_name]
            products = []
            
            # Choose appropriate domain based on location
            domain = self._choose_domain_for_location(site_config['domains'], location_context)
            
            # Build search URL
            search_url = self._build_ecommerce_search_url(domain, site_config, query)
            
            # Scrape the search results
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.request_timeout)
            ) as session:
                try:
                    async with session.get(search_url, headers=self.headers) as response:
                        if response.status == 200:
                            html = await response.text()
                            products = self._parse_ecommerce_results(html, site_config, domain)
                        else:
                            logger.warning(f"Failed to scrape {site_name}: {response.status}")
                
                except asyncio.TimeoutError:
                    logger.warning(f"Timeout scraping {site_name}")
                except Exception as scrape_error:
                    logger.error(f"Error scraping {site_name}: {str(scrape_error)}")
            
            return {
                'success': len(products) > 0,
                'products': products,
                'source': site_name,
                'results_count': len(products),
                'search_url': search_url
            }
            
        except Exception as e:
            logger.error(f"Error searching {site_name}: {str(e)}")
            return {'success': False, 'error': str(e), 'products': []}
    
    def _parse_google_results(self, data: Dict) -> List[Dict]:
        """Parse Google Custom Search results"""
        products = []
        
        try:
            items = data.get('items', [])
            
            for item in items:
                title = item.get('title', '')
                link = item.get('link', '')
                snippet = item.get('snippet', '')
                
                # Try to extract price from snippet
                price_match = re.search(r'[\$₦£€]\s*[\d,]+(?:\.\d{2})?', snippet)
                price = price_match.group() if price_match else None
                
                # Get image if available
                image_url = None
                if 'pagemap' in item and 'cse_image' in item['pagemap']:
                    image_url = item['pagemap']['cse_image'][0].get('src')
                
                product = {
                    'title': title,
                    'url': link,
                    'description': snippet,
                    'price': price,
                    'image_url': image_url,
                    'source': 'google',
                    'confidence': 0.7
                }
                
                products.append(product)
        
        except Exception as e:
            logger.error(f"Error parsing Google results: {str(e)}")
        
        return products[:self.max_results_per_source]
    
    def _parse_bing_results(self, data: Dict) -> List[Dict]:
        """Parse Bing Search API results"""
        products = []
        
        try:
            web_pages = data.get('webPages', {}).get('value', [])
            
            for item in web_pages:
                title = item.get('name', '')
                link = item.get('url', '')
                snippet = item.get('snippet', '')
                
                # Try to extract price from snippet
                price_match = re.search(r'[\$₦£€]\s*[\d,]+(?:\.\d{2})?', snippet)
                price = price_match.group() if price_match else None
                
                product = {
                    'title': title,
                    'url': link,
                    'description': snippet,
                    'price': price,
                    'source': 'bing',
                    'confidence': 0.7
                }
                
                products.append(product)
        
        except Exception as e:
            logger.error(f"Error parsing Bing results: {str(e)}")
        
        return products[:self.max_results_per_source]
    
    def _choose_domain_for_location(self, domains: List[str], location_context: Dict = None) -> str:
        """Choose the best domain based on user location"""
        if not location_context:
            return domains[0]
        
        country_code = location_context.get('country', '').upper()
        
        # Map country codes to preferred domains
        domain_mapping = {
            'NG': ['.com.ng', '.ng'],
            'GB': ['.co.uk', '.uk'],
            'DE': ['.de'],
            'FR': ['.fr'],
            'KE': ['.co.ke'],
            'EG': ['.com.eg']
        }
        
        if country_code in domain_mapping:
            preferred_extensions = domain_mapping[country_code]
            for domain in domains:
                if any(domain.endswith(ext) for ext in preferred_extensions):
                    return domain
        
        # Default to first domain
        return domains[0]
    
    def _build_ecommerce_search_url(self, domain: str, site_config: Dict, query: str) -> str:
        """Build search URL for e-commerce site"""
        base_url = f"https://{domain}{site_config['search_path']}"
        params = {site_config['search_param']: query}
        
        return f"{base_url}?{urlencode(params)}"
    
    def _parse_ecommerce_results(self, html: str, site_config: Dict, domain: str) -> List[Dict]:
        """Parse e-commerce site search results"""
        products = []
        
        try:
            soup = BeautifulSoup(html, 'html.parser')
            selectors = site_config['selectors']
            
            # Find product containers (this is site-specific and may need adjustment)
            product_containers = soup.find_all(['div', 'article'], class_=lambda x: x and any(
                keyword in str(x).lower() for keyword in ['product', 'item', 'result', 'card']
            ))[:self.max_results_per_source]
            
            for container in product_containers:
                try:
                    # Extract title
                    title_elem = container.select_one(selectors['title'])
                    title = title_elem.get_text(strip=True) if title_elem else ''
                    
                    # Extract price
                    price_elem = container.select_one(selectors['price'])
                    price = price_elem.get_text(strip=True) if price_elem else ''
                    
                    # Extract image
                    img_elem = container.select_one(selectors['image'])
                    image_url = None
                    if img_elem:
                        image_url = img_elem.get('src') or img_elem.get('data-src')
                        if image_url and not image_url.startswith('http'):
                            image_url = f"https://{domain}{image_url}"
                    
                    # Extract product URL
                    link_elem = container.find('a')
                    product_url = None
                    if link_elem:
                        href = link_elem.get('href')
                        if href:
                            if href.startswith('http'):
                                product_url = href
                            else:
                                product_url = f"https://{domain}{href}"
                    
                    # Only add if we have at least title
                    if title:
                        product = {
                            'title': title,
                            'price': price,
                            'image_url': image_url,
                            'url': product_url,
                            'source': domain,
                            'confidence': 0.8
                        }
                        products.append(product)
                
                except Exception as parse_error:
                    logger.debug(f"Error parsing individual product: {str(parse_error)}")
                    continue
        
        except Exception as e:
            logger.error(f"Error parsing {domain} results: {str(e)}")
        
        return products
    
    def _deduplicate_and_rank_products(self, products: List[Dict]) -> List[Dict]:
        """Remove duplicates and rank products by relevance"""
        if not products:
            return []
        
        # Remove duplicates based on title similarity
        unique_products = []
        seen_titles = []
        
        for product in products:
            title = product.get('title', '').lower()
            
            # Check if this title is too similar to an existing one
            is_duplicate = False
            for seen_title in seen_titles:
                similarity = self._calculate_text_similarity(title, seen_title)
                if similarity > 0.8:  # 80% similarity threshold
                    is_duplicate = True
                    break
            
            if not is_duplicate:
                unique_products.append(product)
                seen_titles.append(title)
        
        # Rank products by confidence, price availability, and image availability
        def ranking_score(product):
            score = product.get('confidence', 0.5)
            
            # Boost score if price is available
            if product.get('price'):
                score += 0.2
            
            # Boost score if image is available
            if product.get('image_url'):
                score += 0.1
            
            # Boost score if URL is available
            if product.get('url'):
                score += 0.1
            
            return score
        
        # Sort by ranking score (highest first)
        unique_products.sort(key=ranking_score, reverse=True)
        
        return unique_products
    
    def _calculate_text_similarity(self, text1: str, text2: str) -> float:
        """Calculate similarity between two text strings"""
        # Simple similarity calculation using common words
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())
        
        if not words1 or not words2:
            return 0.0
        
        intersection = words1.intersection(words2)
        union = words1.union(words2)
        
        return len(intersection) / len(union) if union else 0.0
    
    async def _verify_and_enhance_links(self, products: List[Dict]) -> None:
        """Verify and enhance product links"""
        verification_tasks = []
        
        for product in products[:10]:  # Limit to first 10 products
            if product.get('url'):
                task = self._verify_single_link(product)
                verification_tasks.append(task)
        
        if verification_tasks:
            await asyncio.gather(*verification_tasks, return_exceptions=True)
    
    async def _verify_single_link(self, product: Dict) -> None:
        """Verify a single product link"""
        try:
            url = product.get('url')
            if not url:
                return
            
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=10)
            ) as session:
                async with session.head(url, headers=self.headers) as response:
                    product['link_verified'] = response.status == 200
                    product['link_status'] = response.status
        
        except Exception as e:
            product['link_verified'] = False
            product['link_error'] = str(e)
    
    async def _run_with_semaphore(self, semaphore: asyncio.Semaphore, coroutine):
        """Run coroutine with semaphore limit"""
        async with semaphore:
            return await coroutine
    
    def _generate_cache_key(
        self, 
        query: str, 
        search_keywords: List[str] = None, 
        location_context: Dict = None
    ) -> str:
        """Generate cache key for web search"""
        import hashlib
        
        cache_data = {
            'query': query,
            'keywords': search_keywords or [],
            'location': location_context or {}
        }
        
        cache_string = json.dumps(cache_data, sort_keys=True)
        cache_hash = hashlib.md5(cache_string.encode()).hexdigest()
        
        return f"web_search_{cache_hash}"
    
    def get_supported_sites(self) -> Dict[str, Any]:
        """Get information about supported e-commerce sites"""
        return {
            site_name: {
                'enabled': config['enabled'],
                'domains': config['domains'],
                'description': f"Search products on {site_name.title()}"
            }
            for site_name, config in self.ecommerce_sites.items()
        }
    
    async def test_search_engines(self) -> Dict[str, Any]:
        """Test all configured search engines"""
        results = {}
        
        for engine_name, config in self.search_engines.items():
            if config['enabled']:
                try:
                    test_result = await self._search_with_engine(engine_name, "test query")
                    results[engine_name] = {
                        'success': test_result.get('success', False),
                        'error': test_result.get('error'),
                        'configured': bool(config.get('api_key'))
                    }
                except Exception as e:
                    results[engine_name] = {
                        'success': False,
                        'error': str(e),
                        'configured': bool(config.get('api_key'))
                    }
        
        return results


# Helper functions
def extract_price_from_text(text: str) -> Optional[str]:
    """Extract price information from text"""
    # Common price patterns
    price_patterns = [
        r'[\$₦£€¥]\s*[\d,]+(?:\.\d{2})?',  # $123.45, ₦1,234.56
        r'[\d,]+(?:\.\d{2})?\s*[\$₦£€¥]',  # 123.45$, 1,234.56₦
        r'USD\s*[\d,]+(?:\.\d{2})?',        # USD 123.45
        r'NGN\s*[\d,]+(?:\.\d{2})?',        # NGN 1,234.56
    ]
    
    for pattern in price_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group().strip()
    
    return None


def clean_product_title(title: str) -> str:
    """Clean and normalize product title"""
    # Remove extra whitespace
    title = re.sub(r'\s+', ' ', title.strip())
    
    # Remove common prefixes/suffixes
    prefixes_to_remove = ['new', 'hot', 'sale', 'deal', 'offer']
    for prefix in prefixes_to_remove:
        if title.lower().startswith(prefix.lower() + ' '):
            title = title[len(prefix) + 1:]
    
    return title.strip()


def is_valid_product_url(url: str) -> bool:
    """Check if URL looks like a valid product page"""
    if not url:
        return False
    
    try:
        parsed = urlparse(url)
        
        # Must have valid scheme and netloc
        if not parsed.scheme or not parsed.netloc:
            return False
        
        # Check for product indicators in URL
        product_indicators = [
            '/product/', '/item/', '/p/', '/dp/', '/products/',
            'product-', 'item-', '/buy/', '/shop/'
        ]
        
        url_lower = url.lower()
        return any(indicator in url_lower for indicator in product_indicators)
    
    except Exception:
        return False