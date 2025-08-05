# external_search_enhanced.py - GLOBAL MARKET INTEGRATION
import requests
import json
import logging
from django.core.cache import cache
from django.conf import settings
import time
import re
from urllib.parse import quote_plus
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

logger = logging.getLogger(__name__)

# Global market configuration
EXTERNAL_STORES = {
    'amazon': {
        'name': 'Amazon Global',
        'base_url': 'https://www.amazon.com',
        'search_endpoint': '/s',
        'currency': 'USD',
        'shipping_info': 'International shipping available to Nigeria',
        'priority': 1,
        'enabled': True
    },
    'jumia': {
        'name': 'Jumia Nigeria',
        'base_url': 'https://www.jumia.com.ng',
        'search_endpoint': '/catalog/',
        'currency': 'NGN',
        'shipping_info': 'Fast delivery in Nigeria',
        'priority': 2,
        'enabled': True
    },
    'konga': {
        'name': 'Konga Nigeria', 
        'base_url': 'https://www.konga.com',
        'search_endpoint': '/search',
        'currency': 'NGN',
        'shipping_info': 'Nigerian local delivery',
        'priority': 3,
        'enabled': True
    },
    'aliexpress': {
        'name': 'AliExpress',
        'base_url': 'https://www.aliexpress.com',
        'search_endpoint': '/wholesale',
        'currency': 'USD',
        'shipping_info': 'Global shipping (7-15 days to Nigeria)',
        'priority': 4,
        'enabled': True
    },
    'ebay': {
        'name': 'eBay Global',
        'base_url': 'https://www.ebay.com',
        'search_endpoint': '/sch/',
        'currency': 'USD',
        'shipping_info': 'International shipping varies',
        'priority': 5,
        'enabled': True
    }
}

# Currency conversion rates (cache for 1 hour)
CURRENCY_RATES = {
    'USD_TO_NGN': 1650.0,  # Updated regularly
    'EUR_TO_NGN': 1750.0,
    'GBP_TO_NGN': 2000.0
}


class ExternalSearchManager:
    """
    ENHANCED: Manages external store searches with global market integration
    """
    
    def __init__(self):
        self.session = requests.Session()
        self.session.timeout = 10
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        })
    
    def search_all_stores(self, query, limit=6, max_workers=3):
        """
        ENHANCED: Search multiple external stores concurrently
        """
        try:
            if not query or len(query.strip()) < 2:
                return []
            
            clean_query = self.clean_search_query(query)
            logger.info(f"🌐 External search for: '{clean_query}'")
            
            # Check cache first
            cache_key = f"external_search_{clean_query}_{limit}"
            cached_results = cache.get(cache_key)
            if cached_results:
                logger.info(f"✅ Using cached external results for '{clean_query}'")
                return cached_results
            
            # Get enabled stores sorted by priority
            enabled_stores = {
                k: v for k, v in EXTERNAL_STORES.items() 
                if v.get('enabled', True)
            }
            
            sorted_stores = sorted(
                enabled_stores.items(), 
                key=lambda x: x[1].get('priority', 999)
            )
            
            all_results = []
            
            # Use thread pool for concurrent searches
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                future_to_store = {
                    executor.submit(
                        self.search_store, 
                        store_name, 
                        store_config, 
                        clean_query, 
                        limit // len(sorted_stores) + 1
                    ): store_name
                    for store_name, store_config in sorted_stores[:5]  # Top 5 stores
                }
                
                for future in as_completed(future_to_store, timeout=15):
                    store_name = future_to_store[future]
                    try:
                        store_results = future.result(timeout=10)
                        if store_results:
                            all_results.extend(store_results)
                            logger.info(f"✅ {store_name}: {len(store_results)} results")
                        else:
                            logger.info(f"⚠️ {store_name}: No results")
                    except Exception as store_error:
                        logger.error(f"❌ {store_name} search failed: {str(store_error)}")
                        continue
            
            # Sort results by relevance and quality
            sorted_results = self.rank_external_results(all_results, clean_query)
            
            # Limit final results
            final_results = sorted_results[:limit]
            
            # Cache successful results for 10 minutes
            if final_results:
                cache.set(cache_key, final_results, timeout=600)
            
            logger.info(f"🌐 External search completed: {len(final_results)} total results")
            return final_results
            
        except Exception as e:
            logger.error(f"External search manager error: {str(e)}")
            return []
    
    def search_store(self, store_name, store_config, query, limit):
        """
        Search individual store with specific implementation
        """
        try:
            if store_name == 'amazon':
                return self.search_amazon(query, limit)
            elif store_name == 'jumia':
                return self.search_jumia(query, limit)
            elif store_name == 'konga':
                return self.search_konga(query, limit)
            elif store_name == 'aliexpress':
                return self.search_aliexpress(query, limit)
            elif store_name == 'ebay':
                return self.search_ebay(query, limit)
            else:
                logger.warning(f"Unknown store: {store_name}")
                return []
                
        except Exception as e:
            logger.error(f"Store search error for {store_name}: {str(e)}")
            return []
    
    def search_amazon(self, query, limit=3):
        """
        ENHANCED: Search Amazon with better parsing
        """
        try:
            search_url = f"https://www.amazon.com/s?k={quote_plus(query)}&ref=sr_pg_1"
            
            response = self.session.get(search_url, timeout=10)
            response.raise_for_status()
            
            # Amazon search results parsing (simplified - real implementation would use proper scraping)
            results = []
            
            # Mock results for demo (replace with actual scraping)
            mock_results = [
                {
                    'name': f'{query.title()} - Amazon Choice',
                    'price': '$29.99',
                    'price_ngn': '₦49,347',
                    'rating': 4.5,
                    'reviews_count': 1250,
                    'image_url': 'https://via.placeholder.com/200x200',
                    'product_url': f'https://amazon.com/dp/B08N5WRWNW',
                    'source': 'Amazon Global',
                    'shipping': 'International shipping to Nigeria available',
                    'availability': 'In Stock',
                    'prime': True
                },
                {
                    'name': f'Premium {query} Set',
                    'price': '$45.99',
                    'price_ngn': '₦75,883',
                    'rating': 4.3,
                    'reviews_count': 892,
                    'image_url': 'https://via.placeholder.com/200x200',
                    'product_url': f'https://amazon.com/dp/B07H9VQM8K',
                    'source': 'Amazon Global',
                    'shipping': 'Ships to Nigeria',
                    'availability': 'In Stock',
                    'prime': False
                }
            ]
            
            return mock_results[:limit]
            
        except Exception as e:
            logger.error(f"Amazon search error: {str(e)}")
            return []
    
    def search_jumia(self, query, limit=3):
        """
        ENHANCED: Search Jumia Nigeria
        """
        try:
            # Jumia API or scraping implementation
            mock_results = [
                {
                    'name': f'{query.title()} - Jumia Deal',
                    'price': '₦25,500',
                    'price_ngn': '₦25,500',
                    'rating': 4.2,
                    'reviews_count': 324,
                    'image_url': 'https://via.placeholder.com/200x200',
                    'product_url': f'https://jumia.com.ng/product/{query}',
                    'source': 'Jumia Nigeria',
                    'shipping': 'Free delivery in Lagos',
                    'availability': 'In Stock',
                    'jumia_express': True
                }
            ]
            
            return mock_results[:limit]
            
        except Exception as e:
            logger.error(f"Jumia search error: {str(e)}")
            return []
    
    def search_konga(self, query, limit=3):
        """
        ENHANCED: Search Konga Nigeria
        """
        try:
            mock_results = [
                {
                    'name': f'{query.title()} - Konga Special',
                    'price': '₦28,900',
                    'price_ngn': '₦28,900',
                    'rating': 4.0,
                    'reviews_count': 156,
                    'image_url': 'https://via.placeholder.com/200x200',
                    'product_url': f'https://konga.com/product/{query}',
                    'source': 'Konga Nigeria',
                    'shipping': 'Konga delivery available',
                    'availability': 'In Stock',
                    'konga_assured': True
                }
            ]
            
            return mock_results[:limit]
            
        except Exception as e:
            logger.error(f"Konga search error: {str(e)}")
            return []
    
    def search_aliexpress(self, query, limit=3):
        """
        ENHANCED: Search AliExpress
        """
        try:
            mock_results = [
                {
                    'name': f'{query.title()} - Global Seller',
                    'price': '$12.99',
                    'price_ngn': '₦21,434',
                    'rating': 4.6,
                    'reviews_count': 2340,
                    'image_url': 'https://via.placeholder.com/200x200',
                    'product_url': f'https://aliexpress.com/item/{query}',
                    'source': 'AliExpress',
                    'shipping': '7-15 days to Nigeria',
                    'availability': 'In Stock',
                    'choice': True
                }
            ]
            
            return mock_results[:limit]
            
        except Exception as e:
            logger.error(f"AliExpress search error: {str(e)}")
            return []
    
    def search_ebay(self, query, limit=3):
        """
        ENHANCED: Search eBay
        """
        try:
            mock_results = [
                {
                    'name': f'{query.title()} - eBay Find',
                    'price': '$22.50',
                    'price_ngn': '₦37,125',
                    'rating': 4.1,
                    'reviews_count': 456,
                    'image_url': 'https://via.placeholder.com/200x200',
                    'product_url': f'https://ebay.com/itm/{query}',
                    'source': 'eBay Global',
                    'shipping': 'International shipping',
                    'availability': 'In Stock',
                    'best_offer': True
                }
            ]
            
            return mock_results[:limit]
            
        except Exception as e:
            logger.error(f"eBay search error: {str(e)}")
            return []
    
    def rank_external_results(self, results, query):
        """
        ENHANCED: Rank external results by relevance and quality
        """
        try:
            if not results:
                return []
            
            query_lower = query.lower()
            
            def calculate_score(result):
                score = 0
                
                # Name relevance
                name = result.get('name', '').lower()
                if query_lower in name:
                    score += 100
                    if name.startswith(query_lower):
                        score += 50
                
                # Rating bonus
                rating = result.get('rating', 0)
                score += rating * 10
                
                # Reviews count bonus (log scale)
                reviews = result.get('reviews_count', 0)
                if reviews > 0:
                    import math
                    score += min(math.log10(reviews) * 10, 30)
                
                # Source priority
                source_priority = {
                    'Amazon Global': 20,
                    'Jumia Nigeria': 15,
                    'Konga Nigeria': 15,
                    'AliExpress': 10,
                    'eBay Global': 8
                }
                source = result.get('source', '')
                score += source_priority.get(source, 0)
                
                # Special features bonus
                if result.get('prime') or result.get('jumia_express') or result.get('choice'):
                    score += 15
                
                return score
            
            # Sort by calculated score
            sorted_results = sorted(results, key=calculate_score, reverse=True)
            
            return sorted_results
            
        except Exception as e:
            logger.error(f"Results ranking error: {str(e)}")
            return results
    
    def clean_search_query(self, query):
        """
        Clean query for external searches
        """
        try:
            if not query:
                return ""
            
            # Remove common stop words
            stop_words = ['the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by']
            
            # Clean and normalize
            cleaned = re.sub(r'[^\w\s]', ' ', query.lower())
            words = [word for word in cleaned.split() if word not in stop_words and len(word) > 2]
            
            return ' '.join(words) if words else query.strip()
            
        except Exception as e:
            logger.error(f"Query cleaning error: {str(e)}")
            return str(query)[:50]


class CurrencyConverter:
    """
    ENHANCED: Handle currency conversion for global marketplace
    """
    
    @staticmethod
    def convert_to_naira(amount_str, from_currency='USD'):
        """
        Convert foreign currency to Nigerian Naira
        """
        try:
            # Extract numeric value from price string
            amount_match = re.search(r'[\d,]+\.?\d*', amount_str.replace(',', ''))
            if not amount_match:
                return amount_str
            
            amount = float(amount_match.group().replace(',', ''))
            
            # Get conversion rate
            rate_key = f"{from_currency.upper()}_TO_NGN"
            rate = CURRENCY_RATES.get(rate_key, 1650.0)  # Default USD rate
            
            # Convert
            naira_amount = amount * rate
            
            return f"₦{naira_amount:,.0f}"
            
        except Exception as e:
            logger.error(f"Currency conversion error: {str(e)}")
            return amount_str
    
    @staticmethod
    def update_exchange_rates():
        """
        Update exchange rates (implement with real API)
        """
        try:
            # Mock implementation - replace with real API call
            # Example: API from exchangerate-api.com or fixer.io
            
            updated_rates = {
                'USD_TO_NGN': 1650.0,
                'EUR_TO_NGN': 1750.0, 
                'GBP_TO_NGN': 2000.0
            }
            
            CURRENCY_RATES.update(updated_rates)
            cache.set('currency_rates', CURRENCY_RATES, timeout=3600)  # Cache for 1 hour
            
            logger.info("Exchange rates updated successfully")
            return True
            
        except Exception as e:
            logger.error(f"Exchange rate update error: {str(e)}")
            return False


class PriceComparison:
    """
    ENHANCED: Compare prices across Finda and external stores
    """
    
    @staticmethod
    def compare_prices(finda_results, external_results):
        """
        Generate price comparison analysis
        """
        try:
            if not finda_results and not external_results:
                return None
            
            comparison = {
                'finda_lowest': None,
                'finda_highest': None,
                'external_lowest': None,
                'external_highest': None,
                'finda_average': 0,
                'external_average': 0,
                'recommendation': '',
                'savings_analysis': {}
            }
            
            # Analyze Finda prices
            finda_prices = []
            for item in finda_results:
                try:
                    is_product = hasattr(item, 'product_name')
                    price = getattr(item, 'product_price' if is_product else 'starting_price', 0)
                    if price > 0:
                        finda_prices.append(float(price))
                except:
                    continue
            
            if finda_prices:
                comparison['finda_lowest'] = min(finda_prices)
                comparison['finda_highest'] = max(finda_prices)
                comparison['finda_average'] = sum(finda_prices) / len(finda_prices)
            
            # Analyze external prices (convert to Naira)
            external_prices = []
            for item in external_results:
                try:
                    price_str = item.get('price_ngn', item.get('price', ''))
                    if '₦' in price_str:
                        price_num = float(re.sub(r'[^\d.]', '', price_str))
                        external_prices.append(price_num)
                except:
                    continue
            
            if external_prices:
                comparison['external_lowest'] = min(external_prices)
                comparison['external_highest'] = max(external_prices)
                comparison['external_average'] = sum(external_prices) / len(external_prices)
            
            # Generate recommendation
            if finda_prices and external_prices:
                finda_avg = comparison['finda_average']
                external_avg = comparison['external_average']
                
                if finda_avg <= external_avg * 1.1:  # Within 10%
                    comparison['recommendation'] = 'finda_better'
                elif external_avg < finda_avg * 0.8:  # External 20% cheaper
                    comparison['recommendation'] = 'external_cheaper'
                else:
                    comparison['recommendation'] = 'comparable'
                    
                # Calculate potential savings
                savings = finda_avg - external_avg
                comparison['savings_analysis'] = {
                    'amount': abs(savings),
                    'percentage': abs(savings / max(finda_avg, external_avg)) * 100,
                    'finda_cheaper': savings < 0
                }
            
            return comparison
            
        except Exception as e:
            logger.error(f"Price comparison error: {str(e)}")
            return None


# Main functions for use in views
def search_external_stores(query, limit=6):
    """
    ENHANCED: Main function to search external stores
    """
    try:
        if not query or len(query.strip()) < 2:
            return []
        
        manager = ExternalSearchManager()
        results = manager.search_all_stores(query, limit)
        
        # Convert prices to Naira for consistency
        for result in results:
            if result.get('price') and '₦' not in result['price']:
                currency = 'USD'  # Default assumption
                if '$' in result['price']:
                    currency = 'USD'
                elif '€' in result['price']:
                    currency = 'EUR'
                elif '£' in result['price']:
                    currency = 'GBP'
                
                converter = CurrencyConverter()
                result['price_ngn'] = converter.convert_to_naira(result['price'], currency)
        
        return results
        
    except Exception as e:
        logger.error(f"External stores search error: {str(e)}")
        return []


def format_external_results(results, query=""):
    """
    ENHANCED: Format external search results for display
    """
    try:
        if not results:
            return "I checked external stores but didn't find good matches right now. Let's focus on our amazing Finda marketplace instead! What else can I help you find? 🛍️"
        
        response_lines = []
        
        # Header with reminder about Finda benefits
        response_lines.append("🌐 Here are some external options as requested (bonus alternatives):\n")
        
        for i, result in enumerate(results[:5], 1):
            try:
                name = result.get('name', 'Product')
                price_ngn = result.get('price_ngn', result.get('price', 'Price available'))
                source = result.get('source', 'External store')
                rating = result.get('rating', 0)
                reviews = result.get('reviews_count', 0)
                shipping = result.get('shipping', 'Shipping info available')
                url = result.get('product_url', '#')
                
                # Format rating
                if rating > 0:
                    stars = "⭐" * min(int(rating), 5)
                    rating_text = f"{stars} {rating}/5 ({reviews} reviews)"
                else:
                    rating_text = "New listing"
                
                response_lines.append(
                    f"<strong>{i}. {name}</strong><br>"
                    f"💰 <strong>Price:</strong> {price_ngn}<br>"
                    f"🏪 <strong>Store:</strong> {source}<br>"
                    f"🚚 <strong>Shipping:</strong> {shipping}<br>"
                    f"{rating_text}<br>"
                    f'🔗 <a href="{url}" target="_blank" rel="noopener noreferrer">View on {source}</a>'
                    "<hr>"
                )
                
            except Exception as item_error:
                logger.error(f"External result formatting error: {str(item_error)}")
                continue
        
        # Add comparison with Finda benefits
        response_lines.append(
            "📊 <strong>Keep in mind:</strong>\n"
            "• 🚚 Finda sellers offer <strong>faster local delivery</strong>\n"
            "• 💬 <strong>Direct communication</strong> with sellers\n"
            "• 🏠 <strong>Support Nigerian businesses</strong>\n"
            "• 💯 <strong>No international shipping delays</strong>\n"
            "• 🔒 <strong>Secure local transactions</strong>\n"
        )
        
        response_lines.append(
            "\n🛍️ Want to see more local options? Let me search Finda again with different keywords!"
        )
        
        return "\n".join(response_lines)
        
    except Exception as e:
        logger.error(f"External results formatting error: {str(e)}")
        return f"Found some external options for '{query}' but having display issues. Try searching Finda again - our local sellers often have better deals and faster delivery!"


def get_price_comparison(finda_results, external_results):
    """
    ENHANCED: Get comprehensive price comparison
    """
    try:
        comparison_engine = PriceComparison()
        return comparison_engine.compare_prices(finda_results, external_results)
        
    except Exception as e:
        logger.error(f"Price comparison error: {str(e)}")
        return None


def get_shipping_info(store_name, location='Nigeria'):
    """
    ENHANCED: Get shipping information for external stores
    """
    try:
        shipping_info = {
            'Amazon Global': {
                'Nigeria': {
                    'available': True,
                    'time': '7-14 business days',
                    'cost': 'Varies by item and weight',
                    'tracking': True,
                    'notes': 'International shipping fees apply'
                }
            },
            'Jumia Nigeria': {
                'Nigeria': {
                    'available': True,
                    'time': '1-3 business days',
                    'cost': 'Free on orders over ₦15,000',
                    'tracking': True,
                    'notes': 'Local delivery available'
                }
            },
            'Konga Nigeria': {
                'Nigeria': {
                    'available': True,
                    'time': '1-5 business days',
                    'cost': 'From ₦500',
                    'tracking': True,
                    'notes': 'Express delivery available'
                }
            },
            'AliExpress': {
                'Nigeria': {
                    'available': True,
                    'time': '7-15 business days',
                    'cost': 'Usually free',
                    'tracking': True,
                    'notes': 'Longer delivery times, tracking may be limited'
                }
            },
            'eBay Global': {
                'Nigeria': {
                    'available': True,
                    'time': '10-20 business days',
                    'cost': 'Varies by seller',
                    'tracking': 'Depends on seller',
                    'notes': 'Shipping varies by individual sellers'
                }
            }
        }
        
        return shipping_info.get(store_name, {}).get(location, {
            'available': False,
            'notes': 'Shipping information not available'
        })
        
    except Exception as e:
        logger.error(f"Shipping info error: {str(e)}")
        return {'available': False, 'notes': 'Shipping information unavailable'}


def validate_external_search_query(query):
    """
    ENHANCED: Validate query for external searches
    """
    try:
        if not query or len(query.strip()) < 2:
            return False, "Query too short for external search"
        
        # Check for prohibited terms (if any)
        prohibited_terms = ['adult', 'weapon', 'drug']  # Add as needed
        query_lower = query.lower()
        
        for term in prohibited_terms:
            if term in query_lower:
                return False, "Query contains prohibited terms"
        
        # Length check
        if len(query) > 100:
            return False, "Query too long for external search"
        
        return True, query.strip()
        
    except Exception as e:
        logger.error(f"External search validation error: {str(e)}")
        return False, "Query validation failed"


def get_external_search_suggestions(query):
    """
    ENHANCED: Get search suggestions for external stores
    """
    try:
        if not query or len(query) < 3:
            return []
        
        # Common product variations and suggestions
        suggestions_map = {
            'phone': ['smartphone', 'mobile phone', 'iPhone', 'Samsung Galaxy', 'Android phone'],
            'laptop': ['notebook', 'computer', 'MacBook', 'Dell laptop', 'HP laptop'],
            'shoes': ['sneakers', 'boots', 'sandals', 'Nike shoes', 'Adidas shoes'],
            'dress': ['clothing', 'women dress', 'formal dress', 'casual dress'],
            'watch': ['smartwatch', 'wristwatch', 'Apple Watch', 'digital watch'],
            'bag': ['handbag', 'backpack', 'purse', 'travel bag', 'school bag']
        }
        
        query_lower = query.lower()
        suggestions = []
        
        for key, values in suggestions_map.items():
            if key in query_lower:
                suggestions.extend(values[:3])  # Top 3 suggestions per category
        
        # Remove duplicates and limit
        unique_suggestions = list(set(suggestions))[:8]
        
        return unique_suggestions
        
    except Exception as e:
        logger.error(f"External suggestions error: {str(e)}")
        return []


def log_external_search_analytics(query, results_count, sources, user_id=None):
    """
    ENHANCED: Log external search analytics
    """
    try:
        analytics_data = {
            'query': str(query)[:100],
            'results_count': int(results_count),
            'sources': sources,
            'user_id': str(user_id) if user_id else None,
            'timestamp': time.time(),
            'success': results_count > 0
        }
        
        # Store in cache for analytics
        cache_key = f"external_search_analytics_{int(time.time() // 3600)}"  # Hourly buckets
        analytics_list = cache.get(cache_key, [])
        analytics_list.append(analytics_data)
        
        # Keep only last 500 entries per hour
        if len(analytics_list) > 500:
            analytics_list = analytics_list[-500:]
        
        cache.set(cache_key, analytics_list, timeout=7200)  # 2 hours
        
        logger.info(f"External search analytics logged: {query} -> {results_count} results from {len(sources)} sources")
        
    except Exception as e:
        logger.error(f"External search analytics error: {str(e)}")


# Utility functions for maintenance
def update_external_store_status():
    """
    ENHANCED: Update external store availability status
    """
    try:
        manager = ExternalSearchManager()
        
        for store_name, config in EXTERNAL_STORES.items():
            try:
                # Test basic connectivity
                test_url = config['base_url']
                response = manager.session.head(test_url, timeout=5)
                
                if response.status_code == 200:
                    config['status'] = 'available'
                    config['last_check'] = time.time()
                else:
                    config['status'] = 'unavailable'
                
            except Exception as store_error:
                logger.error(f"Store status check error for {store_name}: {str(store_error)}")
                config['status'] = 'unavailable'
        
        # Cache updated status
        cache.set('external_stores_status', EXTERNAL_STORES, timeout=1800)  # 30 minutes
        
        logger.info("External store status updated")
        return True
        
    except Exception as e:
        logger.error(f"Store status update error: {str(e)}")
        return False


def get_store_availability():
    """
    ENHANCED: Get current store availability status
    """
    try:
        cached_status = cache.get('external_stores_status', EXTERNAL_STORES)
        
        available_stores = []
        unavailable_stores = []
        
        for store_name, config in cached_status.items():
            if config.get('status') == 'available' and config.get('enabled', True):
                available_stores.append(store_name)
            else:
                unavailable_stores.append(store_name)
        
        return {
            'available': available_stores,
            'unavailable': unavailable_stores,
            'total_stores': len(cached_status),
            'last_updated': cache.get('stores_last_updated', 'Never')
        }
        
    except Exception as e:
        logger.error(f"Store availability check error: {str(e)}")
        return {
            'available': [],
            'unavailable': list(EXTERNAL_STORES.keys()),
            'total_stores': len(EXTERNAL_STORES),
            'last_updated': 'Error'
        }


# Export main functions
__all__ = [
    'search_external_stores',
    'format_external_results', 
    'get_price_comparison',
    'get_shipping_info',
    'validate_external_search_query',
    'get_external_search_suggestions',
    'log_external_search_analytics',
    'update_external_store_status',
    'get_store_availability',
    'ExternalSearchManager',
    'CurrencyConverter',
    'PriceComparison'
]