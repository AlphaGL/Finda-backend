# utils.py - FULLY ENHANCED & BUG-FIXED VERSION
from django.db.models import Q, F, Value, Case, When, IntegerField
from main.models import Products, Services, Category
import re
import logging
from django.db.models.functions import Lower
from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger(__name__)

def clean_search_query(query):
    """
    ENHANCED: Clean and normalize search query for better matching
    """
    try:
        if not query:
            return ""
        
        # Convert to string and strip
        query = str(query).strip()
        
        if len(query) < 1:
            return ""
        
        # Remove special characters but keep alphanumeric and spaces
        cleaned = re.sub(r'[^\w\s]', ' ', query)
        
        # Remove extra whitespace and convert to lowercase
        cleaned = ' '.join(cleaned.split()).lower().strip()
        
        # Remove very common words that don't help with product search
        stop_words = {
            'i', 'need', 'want', 'looking', 'for', 'a', 'an', 'the', 'some', 'any', 
            'find', 'search', 'buy', 'get', 'help', 'me', 'please', 'can', 'you',
            'show', 'tell', 'give', 'am', 'is', 'are', 'was', 'were'
        }
        
        words = cleaned.split()
        meaningful_words = [word for word in words if word not in stop_words and len(word) >= 2]
        
        # If all words were removed, return original cleaned query
        if not meaningful_words:
            return cleaned
        
        return ' '.join(meaningful_words)
        
    except Exception as e:
        logger.error(f"Query cleaning error: {str(e)}")
        return str(query)[:100] if query else ""


def calculate_relevance_score(query, item):
    """
    ENHANCED: Calculate precise relevance score with better matching algorithm
    """
    try:
        if not query or not item:
            return 0
        
        score = 0
        query_lower = query.lower().strip()
        
        # Determine if it's a product or service
        is_product = hasattr(item, 'product_name')
        
        # Get item attributes safely
        try:
            if is_product:
                name = getattr(item, 'product_name', '').lower()
                description = getattr(item, 'product_description', '').lower()
                brand = getattr(item, 'product_brand', '').lower()
                tags = getattr(item, 'tags', '').lower()
            else:
                name = getattr(item, 'service_name', '').lower()
                description = getattr(item, 'service_description', '').lower()
                brand = ""  # Services don't have brands
                tags = getattr(item, 'tags', '').lower()
                
            category_name = getattr(item.category, 'name', '').lower() if hasattr(item, 'category') and item.category else ""
            
        except Exception as attr_error:
            logger.error(f"Attribute error in relevance scoring: {str(attr_error)}")
            return 0
        
        # EXACT MATCHES get highest priority
        if query_lower == name:
            score += 1000  # Exact name match is perfect
        elif query_lower in name:
            if len(query_lower) >= 3:
                # Check if it's at the beginning (higher score)
                if name.startswith(query_lower):
                    score += 800
                else:
                    score += 500
        
        # Brand exact matches (for products)
        if brand and query_lower == brand:
            score += 900
        elif brand and query_lower in brand and len(query_lower) >= 3:
            score += 400
        
        # Category matches
        if category_name and query_lower == category_name:
            score += 300
        elif category_name and query_lower in category_name and len(query_lower) >= 3:
            score += 150
        
        # Multi-word query processing
        query_words = [word for word in query_lower.split() if len(word) >= 3]
        
        for word in query_words:
            # Name word matches
            if word in name:
                if name.startswith(word):
                    score += 200
                else:
                    score += 100
            
            # Brand word matches
            if brand and word in brand:
                score += 150
            
            # Category word matches
            if category_name and word in category_name:
                score += 80
            
            # Tags matches
            if tags and word in tags:
                score += 60
            
            # Description matches (lower priority)
            if description and word in description:
                score += 30
        
        # Quality bonuses
        try:
            rating = item.average_rating() if hasattr(item, 'average_rating') else 0
            if rating > 4.0:
                score += 50
            elif rating > 3.0:
                score += 25
        except:
            pass
        
        # Business feature bonuses
        try:
            if hasattr(item, 'is_featured') and item.is_featured:
                score += 40
            if hasattr(item, 'is_promoted') and item.is_promoted:
                score += 30
        except:
            pass
        
        # Penalty for poor matches
        # If no meaningful word matches, drastically reduce score
        has_meaningful_match = False
        for word in query_words:
            if (word in name or 
                (brand and word in brand) or 
                (category_name and word in category_name) or
                (tags and word in tags)):
                has_meaningful_match = True
                break
        
        if not has_meaningful_match and score < 100:
            score = max(0, score // 10)  # Severely penalize irrelevant results
        
        return score
        
    except Exception as e:
        logger.error(f"Relevance scoring error: {str(e)}")
        return 0


def search_finda_database(query, limit=5):
    """
    ENHANCED: Search products and services with comprehensive error handling
    """
    try:
        if not query or len(str(query).strip()) < 2:
            return []
        
        clean_query = clean_search_query(query)
        if not clean_query:
            return []
        
        logger.info(f"🔍 Searching Finda database for: '{clean_query}'")
        
        # Check cache first
        cache_key = f"search_results_{clean_query}_{limit}"
        cached_results = cache.get(cache_key)
        if cached_results:
            logger.info(f"✅ Found cached results for '{clean_query}'")
            return cached_results
        
        # Get all published products and services with error handling
        try:
            products = Products.objects.filter(
                product_status='published'
            ).select_related('category', 'country', 'state', 'city')
            
            services = Services.objects.filter(
                service_status='published'
            ).select_related('category', 'country', 'state', 'city')
            
        except Exception as db_error:
            logger.error(f"Database query error: {str(db_error)}")
            return []
        
        # Score and filter results
        scored_results = []
        
        # Process products
        try:
            for product in products:
                try:
                    score = calculate_relevance_score(clean_query, product)
                    if score >= 50:  # Only include relevant results
                        scored_results.append((product, score, 'product'))
                except Exception as product_error:
                    logger.error(f"Product scoring error: {str(product_error)}")
                    continue
                    
        except Exception as products_error:
            logger.error(f"Products processing error: {str(products_error)}")
        
        # Process services
        try:
            for service in services:
                try:
                    score = calculate_relevance_score(clean_query, service)
                    if score >= 50:  # Only include relevant results
                        scored_results.append((service, score, 'service'))
                except Exception as service_error:
                    logger.error(f"Service scoring error: {str(service_error)}")
                    continue
                    
        except Exception as services_error:
            logger.error(f"Services processing error: {str(services_error)}")
        
        # Sort by relevance score (highest first)
        try:
            scored_results.sort(key=lambda x: x[1], reverse=True)
        except Exception as sort_error:
            logger.error(f"Results sorting error: {str(sort_error)}")
        
        # Extract items and limit results
        results = []
        try:
            for item_tuple in scored_results[:limit]:
                results.append(item_tuple[0])
        except Exception as extraction_error:
            logger.error(f"Results extraction error: {str(extraction_error)}")
        
        # Cache successful results for 5 minutes
        if results:
            try:
                cache.set(cache_key, results, timeout=300)
            except Exception as cache_error:
                logger.error(f"Cache storage error: {str(cache_error)}")
        
        logger.info(f"✅ Found {len(results)} relevant matches from Finda database")
        if results:
            for i, result in enumerate(results[:3]):
                try:
                    name = getattr(result, 'product_name', getattr(result, 'service_name', 'Unknown'))
                    score = scored_results[i][1] if i < len(scored_results) else 0
                    logger.info(f"   {i+1}. {name} (Score: {score})")
                except:
                    continue
        
        return results
        
    except Exception as e:
        logger.error(f"Search database error: {str(e)}")
        return []


def format_finda_results(results, query="", limit=3):
    """
    ENHANCED: Format Finda results with comprehensive error handling
    """
    try:
        if not results:
            return None
        
        top_results = results[:limit]
        response_lines = []
        
        # Enthusiastic header
        response_lines.append("🛍️ Excellent! I found these amazing options on Finda for you:\n")
        
        for i, obj in enumerate(top_results, 1):
            try:
                # Determine type and extract info safely
                is_product = hasattr(obj, 'product_name')
                
                if is_product:
                    name = getattr(obj, 'product_name', 'Product Name Not Available')
                    try:
                        price_formatted = obj.get_formatted_price() if hasattr(obj, 'get_formatted_price') else f"₦{getattr(obj, 'product_price', 0):,.2f}"
                    except:
                        price_formatted = "Contact for price"
                    
                    try:
                        location = obj.get_full_location() if hasattr(obj, 'get_full_location') else "Location available"
                    except:
                        location = "Location available"
                    
                    try:
                        rating = obj.average_rating() if hasattr(obj, 'average_rating') else 0
                        rating_count = obj.rating_count() if hasattr(obj, 'rating_count') else 0
                    except:
                        rating = 0
                        rating_count = 0
                    
                    try:
                        url = obj.get_absolute_url() if hasattr(obj, 'get_absolute_url') else f"/products/{getattr(obj, 'slug', obj.id)}/"
                    except:
                        url = f"/product/{getattr(obj, 'id', '')}/"
                    
                    # Show discount if available
                    try:
                        discount = obj.get_discount_percentage() if hasattr(obj, 'get_discount_percentage') else 0
                        discount_text = f" 🔥 {discount}% OFF!" if discount > 0 else ""
                    except:
                        discount_text = ""
                    
                else:  # Service
                    name = getattr(obj, 'service_name', 'Service Name Not Available')
                    try:
                        price_formatted = obj.get_formatted_price_range() if hasattr(obj, 'get_formatted_price_range') else "Contact for pricing"
                    except:
                        price_formatted = "Contact for pricing"
                    
                    try:
                        location = obj.get_full_location() if hasattr(obj, 'get_full_location') else "Location available"
                    except:
                        location = "Location available"
                    
                    try:
                        rating = obj.average_rating() if hasattr(obj, 'average_rating') else 0
                        rating_count = obj.rating_count() if hasattr(obj, 'rating_count') else 0
                    except:
                        rating = 0
                        rating_count = 0
                    
                    try:
                        url = obj.get_absolute_url() if hasattr(obj, 'get_absolute_url') else f"/services/{getattr(obj, 'slug', obj.id)}/"
                    except:
                        url = f"/service/{getattr(obj, 'id', '')}/"
                    
                    discount_text = ""
                
                # Format rating display safely
                try:
                    if rating > 0 and rating_count > 0:
                        stars = "⭐" * min(int(rating), 5)
                        rating_text = f"{stars} {rating}/5 ({rating_count} reviews)"
                    else:
                        rating_text = "⭐ New listing - Be the first to review!"
                except:
                    rating_text = "⭐ New listing"
                
                response_lines.append(
                    f"<strong>{i}. {name}</strong>{discount_text}<br>"
                    f"💰 <strong>Price:</strong> {price_formatted}<br>"
                    f"📍 <strong>Location:</strong> {location}<br>"
                    f"{rating_text}<br>"
                    f'🔗 <a href="https://finda-six.vercel.app{url}" target="_blank" rel="noopener noreferrer">View Details</a>'
                    "<hr>"
                )

                
            except Exception as item_error:
                logger.error(f"Error formatting result {i}: {str(item_error)}")
                # Add basic fallback for this item
                try:
                    item_name = getattr(obj, 'product_name', getattr(obj, 'service_name', f'Item {i}'))
                    response_lines.append(f"{i}. {item_name}\n   Contact seller for details\n")
                except:
                    response_lines.append(f"{i}. Item available - Contact for details\n")
                continue
        
        # Add total results count
        total_count = len(results)
        if total_count > limit:
            response_lines.append(f"📊 Plus {total_count - limit} more options available on Finda!\n")
        
        # Promote Finda benefits
        response_lines.append(
            "✨ <strong>Why choose Finda sellers?</strong>\n"
            "• 🚚 Faster delivery\n"
            "• 💬 Direct communication with sellers\n"
            "• 🏠 Support local businesses\n"
            "• 💯 Verified sellers\n"
        )
        
        # Only suggest external as BONUS option
        response_lines.append(
            "\n💡 Want even more options? I can also search external stores like Amazon, Jumia, etc. "
            "as bonus alternatives. Just say 'yes' if you'd like me to check those too!"
        )
        
        return "\n".join(response_lines)
        
    except Exception as e:
        logger.error(f"Results formatting error: {str(e)}")
        # Return basic fallback
        try:
            return f"Found <strong>{len(results)}</strong> items on Finda for <strong>'{query}'</strong>. Contact sellers directly for details!"
        except:
            return "Found several items on Finda! Contact sellers for details."


def generate_no_results_response(query):
    """
    ENHANCED: Better no-results response with smart suggestions
    """
    try:
        # Generate alternative search suggestions
        query_words = str(query).lower().split() if query else []
        suggestions = []
        
        # Common alternatives mapping
        alternatives = {
            'phone': ['mobile', 'smartphone', 'cell phone', 'iPhone', 'Samsung'],
            'laptop': ['computer', 'notebook', 'PC', 'MacBook'],
            'car': ['vehicle', 'automobile', 'auto', 'Toyota', 'Honda'],
            'dress': ['clothing', 'outfit', 'apparel', 'fashion'],
            'repair': ['fix', 'service', 'maintenance', 'technician'],
            'plumber': ['plumbing', 'water', 'pipes', 'bathroom'],
            'electrician': ['electrical', 'wiring', 'power', 'lights'],
            'photographer': ['photography', 'photos', 'camera', 'wedding'],
        }
        
        for word in query_words:
            if word in alternatives:
                suggestions.extend(alternatives[word][:2])  # Take first 2 alternatives
        
        # Remove duplicates and limit
        suggestions = list(set(suggestions))[:3]
        
        suggestion_text = ""
        if suggestions:
            suggestion_text = f"Try searching for: <strong>{', '.join(suggestions)}</strong>"
        else:
            suggestion_text = "Try different keywords or brand names"
        
        return f"""
🔍 I searched our platform thoroughly for <strong>'{query}'</strong> but didn't find exact matches right now.

Don't give up! Here's how I can help:

1️⃣ Try different keywords
   • <strong>{suggestion_text}</strong>
   • Use specific brand names

2️⃣ Browse our categories
   • Type 'categories' to see what's popular
   • Discover similar items you might like

3️⃣ Set up alerts (Coming soon!)
   • Get notified when <strong>'{query}'</strong> arrives on Finda

4️⃣ Search external stores
   • Amazon, Jumia, Konga as backup options

What would you prefer? Say 'categories' to browse, or 'external' to check other stores!
"""
        
    except Exception as e:
        logger.error(f"No results response error: <strong>{str(e)}</strong>")
        return f"I didn't find '{query}' right now. Try different keywords or say 'categories' to browse!"


def search_by_category(category_name, limit=8):
    """
    ENHANCED: Search products and services by category with error handling
    """
    try:
        if not category_name:
            return []
        
        logger.info(f"🔍 Searching by category: <strong>{category_name}</strong>")
        
        # Find category (case insensitive) with error handling
        try:
            category = Category.objects.filter(
                Q(name__icontains=category_name) | Q(slug__icontains=category_name),
                is_active=True
            ).first()
        except Exception as category_error:
            logger.error(f"Category lookup error: {str(category_error)}")
            return []
        
        if not category:
            logger.info(f"Category <strong>'{category_name}'</strong> not found")
            return []
        
        logger.info(f"🔍 Found category: <strong>{category.name}</strong>")
        
        # Get products and services in this category with error handling
        all_items = []
        
        try:
            products = Products.objects.filter(
                category=category,
                product_status='published'
            ).select_related('country', 'state', 'city')[:limit//2]
            
            all_items.extend(list(products))
            
        except Exception as products_error:
            logger.error(f"Products category search error: {str(products_error)}")
        
        try:
            services = Services.objects.filter(
                category=category,
                service_status='published'
            ).select_related('country', 'state', 'city')[:limit//2]
            
            all_items.extend(list(services))
            
        except Exception as services_error:
            logger.error(f"Services category search error: {str(services_error)}")
        
        # Sort by: promoted > featured > rating > recent
        try:
            all_items.sort(key=lambda obj: (
                getattr(obj, 'is_promoted', False),
                getattr(obj, 'is_featured', False),
                obj.average_rating() if hasattr(obj, 'average_rating') else 0,
                getattr(obj, 'created_at', timezone.now())
            ), reverse=True)
        except Exception as sort_error:
            logger.error(f"Category results sorting error: {str(sort_error)}")
        
        return all_items[:limit]
        
    except Exception as e:
        logger.error(f"Category search error: {str(e)}")
        return []


def get_trending_items(limit=6):
    """
    ENHANCED: Get trending products and services with error handling
    """
    try:
        all_trending = []
        
        # Get trending products
        try:
            trending_products = Products.objects.filter(
                product_status='published'
            ).order_by('-views_count', '-favorites_count', '-created_at')[:limit//2]
            
            all_trending.extend(list(trending_products))
            
        except Exception as products_error:
            logger.error(f"Trending products error: {str(products_error)}")
        
        # Get trending services
        try:
            trending_services = Services.objects.filter(
                service_status='published'
            ).order_by('-views_count', '-contacts_count', '-created_at')[:limit//2]
            
            all_trending.extend(list(trending_services))
            
        except Exception as services_error:
            logger.error(f"Trending services error: {str(services_error)}")
        
        # Sort by engagement metrics
        try:
            all_trending.sort(key=lambda obj: (
                getattr(obj, 'views_count', 0),
                obj.average_rating() if hasattr(obj, 'average_rating') else 0,
                getattr(obj, 'created_at', timezone.now())
            ), reverse=True)
        except Exception as sort_error:
            logger.error(f"Trending sort error: {str(sort_error)}")
        
        return all_trending[:limit]
        
    except Exception as e:
        logger.error(f"Trending items error: {str(e)}")
        return []


def format_categories_response():
    """
    ENHANCED: Format categories for browsing with error handling
    """
    try:
        categories = Category.objects.filter(
            is_active=True, 
            parent=None
        ).order_by('sort_order', 'name')
        
        if not categories.exists():
            return "Our categories are being updated. Try searching for specific items instead!"
        
        response_lines = ["🛍️ Browse our Popular Categories:\n"]
        
        for cat in categories:
            try:
                # Count items in category safely
                product_count = 0
                service_count = 0
                
                try:
                    product_count = Products.objects.filter(
                        category=cat, 
                        product_status='published'
                    ).count()
                except:
                    pass
                
                try:
                    service_count = Services.objects.filter(
                        category=cat, 
                        service_status='published'
                    ).count()
                except:
                    pass
                
                total_count = product_count + service_count
                
                # Get emoji safely
                emoji = getattr(cat, 'icon', '📦') if hasattr(cat, 'icon') and cat.icon else "📦"
                
                # Get name safely
                name = getattr(cat, 'name', 'Category')
                
                response_lines.append(f"{emoji} {name} ({total_count} items)")
                
            except Exception as cat_error:
                logger.error(f"Category formatting error: {str(cat_error)}")
                continue
        
        response_lines.append(
            "\n💡 How to search:\n"
            "• Type any category name above\n"
            "• Search for specific items (e.g., products: <strong>'smart watch'</strong>, <strong>'samsung'</strong>, or services: <strong>'plumber'</strong>)\n"
            "• Send me a photo of what you want\n"
            "• Use voice messages to search\n\n"
            "What are you looking for today?"
        )
        
        return "\n".join(response_lines)
        
    except Exception as e:
        logger.error(f"Categories response error: {str(e)}")
        return (
            "Browse our categories by searching for:\n"
            "📱 Electronics, 👗 Fashion, 🏠 Home & Garden, 🚗 Automotive, 💼 Services\n"
            "What interests you?"
        )


def extract_search_terms_from_analysis(analysis_text):
    """
    ENHANCED: Extract relevant search terms from AI image analysis
    """
    try:
        if not analysis_text:
            return ""
        
        # Remove common stop words
        stop_words = {
            # Basic articles, pronouns & conjunctions
            'the', 'and', 'or', 'but', 'if', 'then', 'else', 'when', 'while', 'as', 'than', 'that',
            'this', 'these', 'those', 'it', 'its', 'they', 'them', 'their', 'we', 'us', 'our', 'you',
            'your', 'yours', 'i', 'me', 'my', 'mine', 'he', 'him', 'his', 'she', 'her', 'hers', 'who',
            'whom', 'whose', 'which', 'what', 'where', 'why', 'how', 'a', 'an',

            # Verb auxiliaries & common verbs
            'is', 'are', 'was', 'were', 'be', 'been', 'being', 'am', 'do', 'does', 'did', 'doing',
            'have', 'has', 'had', 'having', 'can', 'could', 'should', 'would', 'shall', 'will', 'may',
            'might', 'must',

            # Prepositions & position words
            'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'from', 'about', 'into', 'over', 'under',
            'between', 'among', 'across', 'through', 'before', 'after', 'during', 'within', 'without',
            'up', 'down', 'off', 'onto', 'out', 'around', 'near', 'above', 'below',

            # Filler and vague search terms
            'image', 'images', 'picture', 'pictures', 'photo', 'photos', 'pic', 'pics', 'see', 'show',
            'look', 'looking', 'find', 'search', 'searched', 'appears', 'display', 'view', 'views',
            'browse', 'check', 'checked',

            # Descriptive but non-essential for matching
            'new', 'latest', 'old', 'older', 'brand', 'best', 'top', 'cheap', 'cheapest', 'expensive',
            'affordable', 'quality', 'high', 'low', 'great', 'good', 'bad', 'better', 'worse',

            # Temporal
            'today', 'yesterday', 'tomorrow', 'now', 'later', 'soon', 'recent', 'recently', 'year',
            'month', 'week', 'day', 'hour', 'minute', 'second', 'season', 'spring', 'summer', 'autumn',
            'fall', 'winter', 'monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday',
            'sunday', 'january', 'february', 'march', 'april', 'may', 'june', 'july', 'august',
            'september', 'october', 'november', 'december',

            # Numbers & ordinals (often irrelevant in fuzzy match unless price)
            'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine', 'ten',
            'first', 'second', 'third', 'fourth', 'fifth', 'sixth', 'seventh', 'eighth', 'ninth', 'tenth',

            # Misc common noise
            'etc', 'etc.', 'ok', 'okay', 'yes', 'no', 'please', 'thanks', 'thank', 'hi', 'hello', 'hey',
            'help', 'info', 'information', 'details', 'detail', 'more', 'less', 'other', 'others',
            'item', 'items', 'thing', 'things', 'stuff', 'product', 'products', 'service', 'services',
        }

        
        # Extract meaningful words
        words = re.findall(r'\b[a-zA-Z]{3,}\b', analysis_text.lower())
        meaningful_words = [word for word in words if word not in stop_words]
        
        # Priority terms (brands, product types, etc.)
        priority_terms = {
            # Electronics
            'phone', 'iphone', 'samsung', 'android', 'smartphone', 'mobile', 'galaxy',
            'laptop', 'computer', 'macbook', 'dell', 'hp', 'lenovo', 'tablet', 'ipad',
            'headphones', 'earphones', 'speaker', 'television', 'monitor', 'keyboard',
            
            # Fashion & Accessories
            'shoes', 'nike', 'adidas', 'sneakers', 'boots', 'sandals', 'heels',
            'dress', 'shirt', 'jeans', 'clothes', 'fashion', 'clothing', 'jacket',
            'watch', 'rolex', 'jewelry', 'necklace', 'ring', 'bracelet',
            'bag', 'handbag', 'backpack', 'luggage', 'purse', 'wallet',
            
            # Automotive
            'car', 'toyota', 'honda', 'mercedes', 'bmw', 'vehicle', 'motorcycle',
            'tire', 'engine', 'battery', 'parts', 'accessories',
            
            # Home & Furniture
            'furniture', 'chair', 'table', 'sofa', 'bed', 'desk', 'cabinet',
            'kitchen', 'refrigerator', 'microwave', 'stove', 'dishwasher',
            'mattress', 'pillow', 'curtain', 'carpet', 'lamp'
        }
        
        # Prioritize important terms
        important_terms = []
        for word in meaningful_words:
            if word in priority_terms and word not in important_terms:
                important_terms.insert(0, word)  # Add to front
            elif word not in important_terms:
                important_terms.append(word)
        
        # Return top 3 most relevant terms
        return ' '.join(important_terms[:3])
        
    except Exception as e:
        logger.error(f"Search terms extraction error: {str(e)}")
        return ""


def search_products_by_analysis(analysis_text, limit=3):
    """
    ENHANCED: Search products using AI analysis results with comprehensive fallback
    """
    try:
        if not analysis_text:
            return []
        
        search_terms = extract_search_terms_from_analysis(analysis_text)
        
        if search_terms:
            logger.info(f"🔍 Image search terms: '{search_terms}'")
            results = search_finda_database(search_terms, limit)
            
            if results:
                return results
            
            # Try individual important words
            words = search_terms.split()
            for word in words:
                if len(word) > 3:
                    results = search_finda_database(word, limit)
                    if results:
                        logger.info(f"✅ Found results with individual word: '{word}'")
                        return results
        
        # Try extracting brand names or product types from analysis
        brand_patterns = [
            r'\b(iphone|samsung|apple|nike|adidas|toyota|honda|sony|lg)\b',
            r'\b(laptop|phone|car|dress|shoes|watch|bag|furniture)\b'
        ]
        
        for pattern in brand_patterns:
            matches = re.findall(pattern, analysis_text.lower())
            for match in matches:
                results = search_finda_database(match, limit)
                if results:
                    logger.info(f"✅ Found results with pattern match: '{match}'")
                    return results
        
        return []
        
    except Exception as e:
        logger.error(f"Analysis-based search error: {str(e)}")
        return []


def validate_search_input(query):
    """
    ENHANCED: Validate and sanitize search input
    """
    try:
        if not query:
            return False, "Search query cannot be empty"
        
        # Convert to string and check length
        query_str = str(query).strip()
        
        if len(query_str) < 1:
            return False, "Search query is too short"
        
        if len(query_str) > 200:
            return False, "Search query is too long (max 200 characters)"
        
        # Check for malicious patterns
        malicious_patterns = [
            r'<script',
            r'javascript:',
            r'sql.*injection',
            r'drop.*table',
            r'delete.*from'
        ]
        
        query_lower = query_str.lower()
        for pattern in malicious_patterns:
            if re.search(pattern, query_lower):
                return False, "Invalid search query"
        
        return True, query_str
        
    except Exception as e:
        logger.error(f"Search validation error: {str(e)}")
        return False, "Search validation failed"


def get_search_suggestions(query):
    """
    ENHANCED: Get search suggestions based on partial query
    """
    try:
        if not query or len(query) < 2:
            return []
        
        # Clean query
        clean_query = clean_search_query(query)
        if not clean_query:
            return []
        
        suggestions = []
        
        # Get suggestions from product names
        try:
            products = Products.objects.filter(
                product_name__icontains=clean_query,
                product_status='published'
            ).values_list('product_name', flat=True)[:5]
            
            suggestions.extend(list(products))
            
        except Exception as products_error:
            logger.error(f"Product suggestions error: {str(products_error)}")
        
        # Get suggestions from service names
        try:
            services = Services.objects.filter(
                service_name__icontains=clean_query,
                service_status='published'
            ).values_list('service_name', flat=True)[:5]
            
            suggestions.extend(list(services))
            
        except Exception as services_error:
            logger.error(f"Service suggestions error: {str(services_error)}")
        
        # Get suggestions from categories
        try:
            categories = Category.objects.filter(
                name__icontains=clean_query,
                is_active=True
            ).values_list('name', flat=True)[:3]
            
            suggestions.extend(list(categories))
            
        except Exception as categories_error:
            logger.error(f"Category suggestions error: {str(categories_error)}")
        
        # Remove duplicates and return top 10
        unique_suggestions = list(set(suggestions))[:10]
        
        return unique_suggestions
        
    except Exception as e:
        logger.error(f"Search suggestions error: {str(e)}")
        return []


def log_search_analytics(query, results_count, user_id=None):
    """
    ENHANCED: Log search analytics for improvement
    """
    try:
        analytics_data = {
            'query': str(query)[:100],
            'results_count': int(results_count),
            'user_id': str(user_id) if user_id else None,
            'timestamp': timezone.now().isoformat(),
            'query_length': len(str(query)),
            'has_results': results_count > 0
        }
        
        # Store in cache for analytics processing
        cache_key = f"search_analytics_{timezone.now().strftime('%Y%m%d_%H')}"
        analytics_list = cache.get(cache_key, [])
        analytics_list.append(analytics_data)
        
        # Keep only last 1000 entries per hour
        if len(analytics_list) > 1000:
            analytics_list = analytics_list[-1000:]
        
        cache.set(cache_key, analytics_list, timeout=3600)
        
    except Exception as e:
        logger.error(f"Search analytics logging error: {str(e)}")


# Export main functions
__all__ = [
    'clean_search_query',
    'calculate_relevance_score', 
    'search_finda_database',
    'format_finda_results',
    'generate_no_results_response',
    'search_by_category',
    'get_trending_items',
    'format_categories_response',
    'extract_search_terms_from_analysis',
    'search_products_by_analysis',
    'validate_search_input',
    'get_search_suggestions',
    'log_search_analytics'
]