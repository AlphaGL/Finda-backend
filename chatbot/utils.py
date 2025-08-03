# utils.py - FIXED: Database-first search with proper relevance scoring
from django.db.models import Q, F, Value, Case, When, IntegerField
from main.models import Products, Services, Category
import re
from django.db.models.functions import Lower

def clean_search_query(query):
    """
    Clean and normalize search query for better matching
    """
    if not query:
        return ""
    
    # Remove special characters but keep alphanumeric and spaces
    cleaned = re.sub(r'[^\w\s]', ' ', query)
    
    # Remove extra whitespace and convert to lowercase
    cleaned = ' '.join(cleaned.split()).lower().strip()
    
    # Remove very common words that don't help with product search
    stop_words = {'i', 'need', 'want', 'looking', 'for', 'a', 'an', 'the', 'some', 'any', 'find', 'search', 'buy', 'get'}
    words = cleaned.split()
    meaningful_words = [word for word in words if word not in stop_words and len(word) >= 2]
    
    return ' '.join(meaningful_words)

def calculate_relevance_score(query, item):
    """
    FIXED: Calculate precise relevance score to prioritize exact matches
    """
    score = 0
    query_lower = query.lower().strip()
    
    # Determine if it's a product or service
    is_product = hasattr(item, 'product_name')
    
    if is_product:
        name = item.product_name.lower()
        description = (item.product_description or "").lower()
        brand = (item.product_brand or "").lower()
        tags = (item.tags or "").lower()
    else:
        name = item.service_name.lower()
        description = (item.service_description or "").lower()
        brand = ""  # Services don't have brands
        tags = (item.tags or "").lower()
    
    category_name = item.category.name.lower()
    
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
    if query_lower == category_name:
        score += 300
    elif query_lower in category_name and len(query_lower) >= 3:
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
        if word in category_name:
            score += 80
        
        # Tags matches
        if word in tags:
            score += 60
        
        # Description matches (lower priority)
        if word in description:
            score += 30
    
    # Quality bonuses
    rating = item.average_rating()
    if rating > 4.0:
        score += 50
    elif rating > 3.0:
        score += 25
    
    # Business feature bonuses
    if hasattr(item, 'is_featured') and item.is_featured:
        score += 40
    if hasattr(item, 'is_promoted') and item.is_promoted:
        score += 30
    
    # Penalty for poor matches
    # If no meaningful word matches, drastically reduce score
    has_meaningful_match = False
    for word in query_words:
        if word in name or (brand and word in brand) or word in category_name:
            has_meaningful_match = True
            break
    
    if not has_meaningful_match and score < 100:
        score = max(0, score // 10)  # Severely penalize irrelevant results
    
    return score

def search_finda_database(query, limit=5):
    """
    ENHANCED: Search products and services with proper relevance scoring
    """
    if not query or len(query.strip()) < 2:
        return []
    
    clean_query = clean_search_query(query)
    if not clean_query:
        return []
    
    print(f"🔍 Searching our platform for: '{clean_query}'")
    
    # Get all published products and services
    products = Products.objects.filter(product_status='published').select_related('category', 'country', 'state', 'city')
    services = Services.objects.filter(service_status='published').select_related('category', 'country', 'state', 'city')
    
    # Score and filter results
    scored_results = []
    
    # Process products
    for product in products:
        score = calculate_relevance_score(clean_query, product)
        if score >= 50:  # Only include relevant results
            scored_results.append((product, score, 'product'))
    
    # Process services
    for service in services:
        score = calculate_relevance_score(clean_query, service)
        if score >= 50:  # Only include relevant results
            scored_results.append((service, score, 'service'))
    
    # Sort by relevance score (highest first)
    scored_results.sort(key=lambda x: x[1], reverse=True)
    
    # Extract items and limit results
    results = [item[0] for item in scored_results[:limit]]
    
    print(f"✅ Found {len(results)} relevant matches from our platform")
    if results:
        for i, result in enumerate(results[:3]):
            name = result.product_name if hasattr(result, 'product_name') else result.service_name
            score = scored_results[i][1]
            print(f"   {i+1}. {name} (Score: {score})")
    
    return results

def format_finda_results(results, query="", limit=3):
    """
    ENHANCED: Format Finda results with proper branding and encouragement
    """
    if not results:
        return None
    
    top_results = results[:limit]
    response_lines = []
    
    # Enthusiastic header
    response_lines.append("🛍️ Excellent! I found these amazing options on our platform for you:\n")
    
    for i, obj in enumerate(top_results, 1):
        # Determine type and extract info
        is_product = hasattr(obj, 'product_name')
        
        if is_product:
            name = obj.product_name
            price_formatted = obj.get_formatted_price()
            location = obj.get_full_location()
            rating = obj.average_rating()
            rating_count = obj.rating_count()
            url = obj.get_absolute_url()
            
            # Show discount if available
            discount = obj.get_discount_percentage()
            discount_text = f" 🔥 {discount}% OFF!" if discount > 0 else ""
            
        else:  # Service
            name = obj.service_name
            price_formatted = obj.get_formatted_price_range()
            location = obj.get_full_location()
            rating = obj.average_rating()
            rating_count = obj.rating_count()
            url = obj.get_absolute_url()
            discount_text = ""
        
        # Format rating display
        if rating > 0 and rating_count > 0:
            stars = "⭐" * min(int(rating), 5)
            rating_text = f"{stars} {rating}/5 ({rating_count} reviews)"
        else:
            rating_text = "⭐ New listing - Be the first to review!"
        
        # Format each result with enthusiasm
        response_lines.append(
            f"{i}. {name}{discount_text}\n"
            f"   💰 Price: {price_formatted}\n"
            f"   📍 Location: {location}\n"
            f"   {rating_text}\n"
            f"   🔗 [View Details & Contact Seller](https://finda-six.vercel.app{url})\n"
        )
    
    # Add total results count
    total_count = len(results)
    if total_count > limit:
        response_lines.append(f"📊 Plus {total_count - limit} more options available on our platform!\n")
    
    # Promote Finda benefits
    response_lines.append(
        "✨ Why choose our sellers?\n"
        "• 🚚 Faster delivery\n"
        "• 💬 Direct communication with sellers\n"
        "• 🏠 Support businesses\n"
        "• 💯 Verified Worldwide sellers\n"
    )
    
    # Only suggest external as BONUS option
    response_lines.append(
        "\n💡 Want even more options? I can also search external stores like Amazon, Jumia, etc. "
        "as bonus alternatives. Just say 'yes' if you'd like me to check those too!"
    )
    
    return "\n".join(response_lines)

def generate_no_results_response(query):
    """
    ENHANCED: Better no-results response that keeps users on Finda
    """
    return (
        f"🔍 I searched our platform thoroughly for '{query}' but didn't find exact matches right now.\n\n"
        f"Don't give up! Here's how I can help:\n\n"
        f"1️⃣ Try different keywords\n"
        f"   • Maybe 'phone' instead of 'smartphone'\n"
        f"   • Or 'laptop' instead of 'computer'\n\n"
        f"2️⃣ Browse our categories\n"
        f"   • Type 'categories' to see what's popular\n"
        f"   • Discover similar items you might like\n\n"
        f"3️⃣ Set up a search alert (Coming soon!)\n"
        f"   • Get notified when '{query}' arrives\n\n"
        f"4️⃣ Search external stores\n"
        f"   • Amazon, Jumia, Konga as backup options\n\n"
        f"What would you prefer? Say 'categories' to browse, or 'external' to check other stores!"
    )

def search_by_category(category_name, limit=8):
    """
    ENHANCED: Search products and services by category
    """
    try:
        # Find category (case insensitive)
        category = Category.objects.filter(
            Q(name__icontains=category_name) | Q(slug__icontains=category_name),
            is_active=True
        ).first()
        
        if not category:
            return []
        
        print(f"🔍 Searching category: {category.name}")
        
        # Get products and services in this category
        products = Products.objects.filter(
            category=category,
            product_status='published'
        ).select_related('country', 'state', 'city')[:limit//2]
        
        services = Services.objects.filter(
            category=category,
            service_status='published'
        ).select_related('country', 'state', 'city')[:limit//2]
        
        # Combine and sort by rating and promotion status
        all_items = list(products) + list(services)
        
        # Sort by: promoted > featured > rating > recent
        all_items.sort(key=lambda obj: (
            getattr(obj, 'is_promoted', False),
            getattr(obj, 'is_featured', False),
            obj.average_rating(),
            obj.created_at
        ), reverse=True)
        
        return all_items[:limit]
        
    except Exception as e:
        print(f"❌ Category search error: {e}")
        return []

def get_trending_items(limit=6):
    """
    Get trending products and services based on views and ratings
    """
    # Get trending products
    trending_products = Products.objects.filter(
        product_status='published'
    ).order_by('-views_count', '-favorites_count', '-created_at')[:limit//2]
    
    # Get trending services
    trending_services = Services.objects.filter(
        service_status='published'
    ).order_by('-views_count', '-contacts_count', '-created_at')[:limit//2]
    
    # Combine and sort
    all_trending = list(trending_products) + list(trending_services)
    all_trending.sort(key=lambda obj: (
        getattr(obj, 'views_count', 0),
        obj.average_rating(),
        obj.created_at
    ), reverse=True)
    
    return all_trending[:limit]

def format_categories_response():
    """
    Format categories for browsing
    """
    categories = Category.objects.filter(
        is_active=True, 
        parent=None
    ).order_by('sort_order', 'name')
    
    if not categories.exists():
        return "No categories available right now."
    
    response_lines = ["🛍️ Browse our Popular Categories:\n"]
    
    for cat in categories:
        # Count items in category
        product_count = Products.objects.filter(category=cat, product_status='published').count()
        service_count = Services.objects.filter(category=cat, service_status='published').count()
        total_count = product_count + service_count
        
        emoji = cat.icon if cat.icon else "📦"
        response_lines.append(f"{emoji} {cat.name} ({total_count} items)")
    
    response_lines.append(
        "\n💡 How to search:\n"
        "• Type any category name above\n"
        "• Search for specific items (e.g., 'iPhone', 'plumber')\n"
        "• Send me a photo of what you want\n"
        "• Use voice messages to search\n\n"
        "What are you looking for today?"
    )
    
    return "\n".join(response_lines)

def extract_search_terms_from_analysis(analysis_text):
    """
    Extract relevant search terms from AI image analysis
    """
    if not analysis_text:
        return ""
    
    # Remove common stop words
    stop_words = {
        'the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by',
        'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had',
        'image', 'picture', 'photo', 'see', 'show', 'find', 'search', 'looking', 'appears'
    }
    
    # Extract meaningful words
    words = re.findall(r'\b[a-zA-Z]{3,}\b', analysis_text.lower())
    meaningful_words = [word for word in words if word not in stop_words]
    
    # Priority terms (brands, product types, etc.)
    priority_terms = {
        'phone', 'iphone', 'samsung', 'android', 'smartphone', 'mobile',
        'laptop', 'computer', 'macbook', 'dell', 'hp', 'lenovo',
        'shoes', 'nike', 'adidas', 'sneakers', 'boots', 'sandals',
        'dress', 'shirt', 'jeans', 'clothes', 'fashion', 'clothing',
        'car', 'toyota', 'honda', 'mercedes', 'bmw', 'vehicle',
        'watch', 'rolex', 'apple', 'smartwatch', 'jewelry',
        'bag', 'handbag', 'backpack', 'luggage', 'purse',
        'furniture', 'chair', 'table', 'sofa', 'bed', 'desk'
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

def search_products_by_analysis(analysis_text, limit=3):
    """
    Search products using AI analysis results with fallback
    """
    search_terms = extract_search_terms_from_analysis(analysis_text)
    
    if search_terms:
        print(f"🔍 Image search terms: '{search_terms}'")
        results = search_finda_database(search_terms, limit)
        
        if results:
            return results
        
        # Try individual important words
        words = search_terms.split()
        for word in words:
            if len(word) > 3:
                results = search_finda_database(word, limit)
                if results:
                    return results
    
    return []