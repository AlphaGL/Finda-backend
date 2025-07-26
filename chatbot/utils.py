# utils.py - Enhanced with multimedia search support
from django.db.models import Q
from main.models import Products, Services
import re

def find_exact_matches(text, limit=3):
    """Find exact matches in products and services"""
    qs_prod = Products.objects.filter(
        product_status='published'
    ).filter(
        Q(product_name__icontains=text) |
        Q(product_description__icontains=text) |
        Q(product_brand__icontains=text)
    )
    qs_serv = Services.objects.filter(
        service_status='published'
    ).filter(
        Q(service_name__icontains=text) |
        Q(service_description__icontains=text)
    )
    # combine QuerySets, annotate rating, sort descending
    items = list(qs_prod) + list(qs_serv)
    # sort by rating (Products and Services both have .average_rating())
    items.sort(key=lambda obj: obj.average_rating(), reverse=True)
    return items[:limit]

def find_partial_matches(text, limit=3):
    """Find partial matches using first keyword"""
    first = text.split()[0]
    return find_exact_matches(first, limit)

def extract_search_terms_from_analysis(analysis_text):
    """
    Extract search terms from image/voice analysis text
    """
    # Simple keyword extraction - you can enhance this with NLP
    common_words = ['the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'a', 'an']
    
    # Remove common words and extract meaningful terms
    words = re.findall(r'\b[a-zA-Z]{3,}\b', analysis_text.lower())
    search_terms = [word for word in words if word not in common_words]
    
    # Return top 5 most relevant terms
    return ' '.join(search_terms[:5])

def search_products_by_analysis(analysis_text, limit=3):
    """
    Search products using AI analysis results
    """
    search_terms = extract_search_terms_from_analysis(analysis_text)
    if search_terms:
        return find_exact_matches(search_terms, limit)
    return []