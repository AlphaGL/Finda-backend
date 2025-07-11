from django.db.models import Q
from main.models import Products, Services

def find_exact_matches(text, limit=3):
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
    # e.g. search only by first keyword
    first = text.split()[0]
    return find_exact_matches(first, limit)
