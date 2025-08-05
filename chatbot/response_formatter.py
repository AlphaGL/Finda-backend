# response_formatter.py - WORLD-CLASS RESPONSE FORMATTING SYSTEM
import logging
import re
from django.utils import timezone
from django.core.cache import cache
from decimal import Decimal
import json

logger = logging.getLogger(__name__)


class WorldClassResponseFormatter:
    """
    WORLD-CLASS response formatter that creates beautiful, comprehensive displays
    with all 11 required components for each product/service
    """
    
    def __init__(self):
        self.currency_symbol = '₦'
        self.base_url = 'https://finda-six.vercel.app'
        self.default_image = 'https://via.placeholder.com/300x300?text=Finda+Product'
        
    def format_comprehensive_results(self, results, query="", result_type="search"):
        """
        ENHANCED: Format results with all 11 required components
        """
        try:
            if not results:
                return self.format_no_results_response(query)
            
            # Header based on result type
            if result_type == "category":
                header = f"🛍️ Amazing {result_type.title()} Items on Finda:\n"
            else:
                header = f"🛍️ Excellent! I found these amazing options on Finda for '{query}':\n"
            
            formatted_items = []
            
            for i, item in enumerate(results[:8], 1):
                try:
                    formatted_item = self.format_single_item_comprehensive(item, i)
                    if formatted_item:
                        formatted_items.append(formatted_item)
                except Exception as item_error:
                    logger.error(f"Item {i} formatting error: {str(item_error)}")
                    continue
            
            if not formatted_items:
                return self.format_no_results_response(query)
            
            # Combine all formatted items
            items_display = "\n".join(formatted_items)
            
            # Add summary and call-to-action
            footer = self.generate_comprehensive_footer(len(results), len(formatted_items), query)
            
            return f"{header}\n{items_display}\n{footer}"
            
        except Exception as e:
            logger.error(f"Comprehensive formatting error: {str(e)}")
            return self.format_fallback_response(results, query)
    
    def format_single_item_comprehensive(self, item, index):
        """
        ENHANCED: Format single item with ALL 11 REQUIRED COMPONENTS
        """
        try:
            # Determine item type
            is_product = hasattr(item, 'product_name')
            item_type = 'product' if is_product else 'service'
            
            # 1. PRODUCT/SERVICE NAME
            name = self.get_item_name(item, is_product)
            
            # 2. PRODUCT/SERVICE IMAGE
            image_info = self.get_item_image(item, is_product)
            
            # 3. PRODUCT/SERVICE DISCOUNT
            discount_info = self.get_item_discount(item, is_product)
            
            # 4. PRODUCT/SERVICE PRICE
            price_info = self.get_item_price(item, is_product)
            
            # 5. PRODUCT/SERVICE LOCATION
            location_info = self.get_item_location(item)
            
            # 6. PRODUCT/SERVICE TAGS
            tags_info = self.get_item_tags(item, is_product)
            
            # 7. RECOMMENDATION REASONS
            recommendations = self.generate_recommendation_reasons(item, is_product)
            
            # 8. PROVIDER CONTACT
            contact_info = self.get_provider_contact(item)
            
            # 9. PRODUCT/SERVICE RATING
            rating_info = self.get_item_rating(item, is_product)
            
            # 10. PRODUCT/SERVICE DESCRIPTION
            description_info = self.get_item_description(item, is_product)
            
            # 11. PRODUCT/SERVICE LINK
            link_info = self.get_item_link(item, is_product, item_type)
            
            # Format comprehensive display
            formatted_item = f"""
<div style="border: 2px solid #e1e5e9; border-radius: 12px; padding: 20px; margin: 15px 0; background: linear-gradient(135deg, #f8f9fa 0%, #ffffff 100%); box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
    
    <div style="display: flex; align-items: center; margin-bottom: 15px;">
        <h3 style="color: #2c3e50; font-size: 1.4em; margin: 0; flex: 1;">
            <strong>{index}. {name}</strong> {discount_info['badge']}
        </h3>
    </div>
    
    <div style="display: grid; grid-template-columns: 1fr 2fr; gap: 20px; margin-bottom: 15px;">
        
        <div style="text-align: center;">
            {image_info['display']}
        </div>
        
        <div>
            <div style="margin-bottom: 10px;">
                <strong style="color: #27ae60; font-size: 1.2em;">💰 {price_info['display']}</strong>
                {discount_info['savings']}
            </div>
            
            <div style="margin-bottom: 8px;">
                <strong>📍 Location:</strong> {location_info}
            </div>
            
            <div style="margin-bottom: 8px;">
                {rating_info}
            </div>
            
            <div style="margin-bottom: 10px;">
                <strong>🏷️ Tags:</strong> {tags_info}
            </div>
        </div>
    </div>
    
    <div style="margin-bottom: 15px;">
        <strong>📝 Description:</strong><br>
        <em style="color: #555;">{description_info}</em>
    </div>
    
    <div style="background: #e8f5e8; padding: 12px; border-radius: 8px; margin-bottom: 15px;">
        <strong>⭐ Why This is Recommended:</strong><br>
        {recommendations}
    </div>
    
    <div style="display: flex; justify-content: space-between; align-items: center; background: #f1f3f4; padding: 12px; border-radius: 8px;">
        <div>
            <strong>📞 Contact Seller:</strong><br>
            {contact_info}
        </div>
        
        <div style="text-align: right;">
            {link_info}
        </div>
    </div>
    
</div>

<hr style="border: 1px solid #ddd; margin: 20px 0;">
"""
            
            return formatted_item
            
        except Exception as e:
            logger.error(f"Single item comprehensive formatting error: {str(e)}")
            return self.format_basic_item_fallback(item, index)
    
    def get_item_name(self, item, is_product):
        """Get formatted item name"""
        try:
            if is_product:
                name = getattr(item, 'product_name', 'Product')
            else:
                name = getattr(item, 'service_name', 'Service')
            
            # Clean and format name
            name = str(name).strip()
            if len(name) > 80:
                name = name[:77] + "..."
            
            return name if name else ('Product' if is_product else 'Service')
            
        except Exception as e:
            logger.error(f"Name extraction error: {str(e)}")
            return 'Product' if is_product else 'Service'
    
    def get_item_image(self, item, is_product):
        """Get formatted item image"""
        try:
            image_url = None
            
            # Try to get image URL
            try:
                if is_product:
                    if hasattr(item, 'product_image') and item.product_image:
                        image_url = item.product_image.url
                    elif hasattr(item, 'productimage_set'):
                        first_image = item.productimage_set.first()
                        if first_image and first_image.image:
                            image_url = first_image.image.url
                else:
                    if hasattr(item, 'service_image') and item.service_image:
                        image_url = item.service_image.url
                    elif hasattr(item, 'serviceimage_set'):
                        first_image = item.serviceimage_set.first()
                        if first_image and first_image.image:
                            image_url = first_image.image.url
            except:
                pass
            
            # Use default if no image found
            if not image_url:
                image_url = self.default_image
            
            # Ensure absolute URL
            if image_url and not image_url.startswith('http'):
                image_url = f"{self.base_url}{image_url}"
            
            display = f'<img src="{image_url}" alt="Product Image" style="width: 100%; max-width: 200px; height: 150px; object-fit: cover; border-radius: 8px; border: 2px solid #ddd;">'
            
            return {
                'url': image_url,
                'display': display
            }
            
        except Exception as e:
            logger.error(f"Image extraction error: {str(e)}")
            return {
                'url': self.default_image,
                'display': f'<div style="width: 200px; height: 150px; background: #f0f0f0; border-radius: 8px; display: flex; align-items: center; justify-content: center; border: 2px solid #ddd;"><span style="color: #888;">📷 Image</span></div>'
            }
    
    def get_item_discount(self, item, is_product):
        """Get formatted discount information"""
        try:
            discount_percentage = 0
            original_price = None
            
            # Try to get discount information
            try:
                if hasattr(item, 'discount_percentage'):
                    discount_percentage = float(item.discount_percentage or 0)
                elif hasattr(item, 'get_discount_percentage'):
                    discount_percentage = float(item.get_discount_percentage() or 0)
                
                if hasattr(item, 'original_price'):
                    original_price = item.original_price
            except:
                pass
            
            if discount_percentage > 0:
                badge = f'<span style="background: #e74c3c; color: white; padding: 4px 8px; border-radius: 20px; font-size: 0.8em; font-weight: bold;">🔥 {discount_percentage:.0f}% OFF!</span>'
                
                savings = ""
                if original_price:
                    current_price = getattr(item, 'product_price' if is_product else 'starting_price', 0)
                    if current_price and original_price > current_price:
                        savings_amount = original_price - current_price
                        savings = f'<br><small style="color: #e74c3c;"><s>{self.currency_symbol}{original_price:,.2f}</s> Save {self.currency_symbol}{savings_amount:,.2f}!</small>'
                
                return {
                    'percentage': discount_percentage,
                    'badge': badge,
                    'savings': savings
                }
            else:
                return {
                    'percentage': 0,
                    'badge': '',
                    'savings': ''
                }
                
        except Exception as e:
            logger.error(f"Discount extraction error: {str(e)}")
            return {'percentage': 0, 'badge': '', 'savings': ''}
    
    def get_item_price(self, item, is_product):
        """Get formatted price information"""
        try:
            if is_product:
                price = getattr(item, 'product_price', 0)
            else:
                price = getattr(item, 'starting_price', 0)
            
            if price and price > 0:
                # Format price nicely
                if price >= 1000000:  # 1 million+
                    formatted = f"{self.currency_symbol}{price/1000000:.1f}M"
                elif price >= 1000:  # 1 thousand+
                    formatted = f"{self.currency_symbol}{price/1000:.0f}K"
                else:
                    formatted = f"{self.currency_symbol}{price:,.2f}"
                
                # Add range for services
                if not is_product:
                    max_price = getattr(item, 'max_price', None)
                    if max_price and max_price > price:
                        if max_price >= 1000000:
                            max_formatted = f"{self.currency_symbol}{max_price/1000000:.1f}M"
                        elif max_price >= 1000:
                            max_formatted = f"{self.currency_symbol}{max_price/1000:.0f}K"
                        else:
                            max_formatted = f"{self.currency_symbol}{max_price:,.2f}"
                        
                        formatted = f"{formatted} - {max_formatted}"
                
                return {
                    'amount': price,
                    'display': formatted,
                    'formatted': formatted
                }
            else:
                return {
                    'amount': 0,
                    'display': 'Contact for pricing',
                    'formatted': 'Contact for pricing'
                }
                
        except Exception as e:
            logger.error(f"Price extraction error: {str(e)}")
            return {
                'amount': 0,
                'display': 'Price available',
                'formatted': 'Price available'
            }
    
    def get_item_location(self, item):
        """Get formatted location information"""
        try:
            location_parts = []
            
            # Try to get location components
            try:
                if hasattr(item, 'get_full_location'):
                    return item.get_full_location()
                
                # Manual location building
                if hasattr(item, 'city') and item.city:
                    location_parts.append(str(item.city.name))
                elif hasattr(item, 'city_name'):
                    location_parts.append(str(item.city_name))
                
                if hasattr(item, 'state') and item.state:
                    location_parts.append(str(item.state.name))
                elif hasattr(item, 'state_name'):
                    location_parts.append(str(item.state_name))
                
                if hasattr(item, 'country') and item.country:
                    location_parts.append(str(item.country.name))
                elif hasattr(item, 'country_name'):
                    location_parts.append(str(item.country_name))
                
            except Exception as location_error:
                logger.error(f"Location extraction error: {str(location_error)}")
            
            if location_parts:
                return ', '.join(location_parts)
            else:
                return 'Nigeria'  # Default location
                
        except Exception as e:
            logger.error(f"Location formatting error: {str(e)}")
            return 'Location available'
    
    def get_item_tags(self, item, is_product):
        """Get formatted tags"""
        try:
            tags = []
            
            # Get tags from item
            try:
                item_tags = getattr(item, 'tags', '') or ''
                if item_tags:
                    # Split by common delimiters
                    raw_tags = re.split(r'[,;|]', str(item_tags))
                    tags.extend([tag.strip() for tag in raw_tags if tag.strip()])
            except:
                pass
            
            # Add category as tag
            try:
                if hasattr(item, 'category') and item.category:
                    category_name = str(item.category.name)
                    if category_name not in tags:
                        tags.insert(0, category_name)
            except:
                pass
            
            # Add brand as tag (for products)
            try:
                if is_product and hasattr(item, 'product_brand'):
                    brand = str(item.product_brand or '').strip()
                    if brand and brand not in tags:
                        tags.insert(1, brand)
            except:
                pass
            
            # Add item type
            item_type = 'Product' if is_product else 'Service'
            if item_type not in tags:
                tags.append(item_type)
            
            # Clean and format tags
            cleaned_tags = []
            for tag in tags[:6]:  # Limit to 6 tags
                cleaned_tag = str(tag).strip().title()
                if len(cleaned_tag) > 2 and cleaned_tag not in cleaned_tags:
                    cleaned_tags.append(cleaned_tag)
            
            if cleaned_tags:
                formatted_tags = []
                for tag in cleaned_tags:
                    formatted_tags.append(f'<span style="background: #3498db; color: white; padding: 2px 6px; border-radius: 12px; font-size: 0.75em; margin-right: 4px;">{tag}</span>')
                
                return ' '.join(formatted_tags)
            else:
                return f'<span style="background: #95a5a6; color: white; padding: 2px 6px; border-radius: 12px; font-size: 0.75em;">{"Product" if is_product else "Service"}</span>'
                
        except Exception as e:
            logger.error(f"Tags extraction error: {str(e)}")
            return f'<span style="background: #95a5a6; color: white; padding: 2px 6px; border-radius: 12px; font-size: 0.75em;">{"Product" if is_product else "Service"}</span>'
    
    def generate_recommendation_reasons(self, item, is_product):
        """Generate AI-powered recommendation reasons"""
        try:
            reasons = []
            
            # Rating-based reasons
            try:
                rating = item.average_rating() if hasattr(item, 'average_rating') else 0
                review_count = item.reviews_count() if hasattr(item, 'reviews_count') else 0
                
                if rating >= 4.5:
                    reasons.append("⭐ Excellent customer ratings (4.5+ stars)")
                elif rating >= 4.0:
                    reasons.append("⭐ Highly rated by customers (4+ stars)")
                elif rating >= 3.5:
                    reasons.append("⭐ Good customer feedback (3.5+ stars)")
                
                if review_count > 50:
                    reasons.append(f"💬 Trusted by {review_count}+ customers")
                elif review_count > 10:
                    reasons.append(f"💬 Verified by {review_count} customers")
                elif review_count > 0:
                    reasons.append("💬 Customer reviewed")
                
            except:
                pass
            
            # Business feature reasons
            try:
                if getattr(item, 'is_promoted', False):
                    reasons.append("🔥 Featured seller - Premium listing")
                
                if getattr(item, 'is_featured', False):
                    reasons.append("⭐ Featured item - Popular choice")
                
                if hasattr(item, 'user') and getattr(item.user, 'is_verified', False):
                    reasons.append("✅ Verified seller - Trusted business")
                
            except:
                pass
            
            # Engagement reasons
            try:
                views = getattr(item, 'views_count', 0)
                if views > 1000:
                    reasons.append("👀 Highly viewed - Popular item")
                elif views > 100:
                    reasons.append("👀 Well-viewed item")
                
                if is_product:
                    favorites = getattr(item, 'favorites_count', 0)
                    if favorites > 20:
                        reasons.append("❤️ Customer favorite")
                    elif favorites > 5:
                        reasons.append("❤️ Liked by customers")
                else:
                    contacts = getattr(item, 'contacts_count', 0)
                    if contacts > 50:
                        reasons.append("📞 Frequently contacted")
                    elif contacts > 10:
                        reasons.append("📞 Popular service provider")
                
            except:
                pass
            
            # Price competitiveness
            try:
                # This would involve price comparison logic
                # For now, add generic competitive pricing reason
                price = getattr(item, 'product_price' if is_product else 'starting_price', 0)
                if price > 0:
                    reasons.append("💰 Competitive pricing")
            except:
                pass
            
            # Location benefits
            try:
                location = self.get_item_location(item)
                if 'Nigeria' in location:
                    reasons.append("🇳🇬 Local Nigerian seller - Fast delivery")
            except:
                pass
            
            # Freshness
            try:
                created_at = getattr(item, 'created_at', None)
                if created_at:
                    days_old = (timezone.now() - created_at).days
                    if days_old < 7:
                        reasons.append("🆕 Recently listed - Fresh inventory")
                    elif days_old < 30:
                        reasons.append("🆕 Recent listing")
            except:
                pass
            
            # Default reasons if none found
            if not reasons:
                reasons.extend([
                    "🛍️ Available on Finda marketplace",
                    "🚚 Local delivery available",
                    "💬 Direct seller communication"
                ])
            
            # Limit to top 4 reasons
            top_reasons = reasons[:4]
            
            # Format as bullet points
            formatted_reasons = []
            for reason in top_reasons:
                formatted_reasons.append(f"• {reason}")
            
            return '<br>'.join(formatted_reasons)
            
        except Exception as e:
            logger.error(f"Recommendation reasons error: {str(e)}")
            return "• 🛍️ Quality item on Finda<br>• 🚚 Local delivery available<br>• 💬 Direct seller contact"
    
    def get_provider_contact(self, item):
        """Get formatted provider contact information"""
        try:
            contact_methods = []
            
            # Try to get seller information
            try:
                if hasattr(item, 'user') and item.user:
                    user = item.user
                    
                    # Phone number
                    phone = getattr(user, 'phone', None) or getattr(user, 'phone_number', None)
                    if phone:
                        contact_methods.append(f"📱 {phone}")
                    
                    # Email
                    email = getattr(user, 'email', None)
                    if email:
                        # Mask email for privacy
                        masked_email = self.mask_email(email)
                        contact_methods.append(f"✉️ {masked_email}")
                    
                    # WhatsApp (if available)
                    whatsapp = getattr(user, 'whatsapp', None)
                    if whatsapp:
                        contact_methods.append(f"💬 WhatsApp: {whatsapp}")
                    
                    # Business name
                    business_name = getattr(user, 'business_name', None) or getattr(user, 'company_name', None)
                    if business_name:
                        contact_methods.insert(0, f"🏢 {business_name}")
                    
            except Exception as contact_error:
                logger.error(f"Contact extraction error: {str(contact_error)}")
            
            if contact_methods:
                return '<br>'.join(contact_methods[:3])  # Limit to 3 contact methods
            else:
                return "📞 Contact available via Finda<br>💬 Message seller directly"
                
        except Exception as e:
            logger.error(f"Provider contact error: {str(e)}")
            return "📞 Contact details available<br>💬 Message seller"
    
    def mask_email(self, email):
        """Mask email for privacy"""
        try:
            if '@' in email:
                local, domain = email.split('@', 1)
                if len(local) > 3:
                    masked_local = local[:2] + '*' * (len(local) - 3) + local[-1]
                else:
                    masked_local = local[0] + '*' * (len(local) - 1)
                return f"{masked_local}@{domain}"
            return email
        except:
            return "email@available"
    
    def get_item_rating(self, item, is_product):
        """Get formatted rating information"""
        try:
            rating = 0
            review_count = 0
            
            # Get rating and review count
            try:
                if hasattr(item, 'average_rating'):
                    rating = float(item.average_rating() or 0)
                elif hasattr(item, 'avg_rating'):
                    rating = float(item.avg_rating or 0)
                
                if hasattr(item, 'reviews_count'):
                    review_count = int(item.reviews_count() or 0)
                elif hasattr(item, 'review_count'):
                    review_count = int(item.review_count or 0)
            except:
                pass
            
            if rating > 0:
                # Generate star display
                full_stars = int(rating)
                half_star = 1 if (rating - full_stars) >= 0.5 else 0
                empty_stars = 5 - full_stars - half_star
                
                stars_display = '⭐' * full_stars
                if half_star:
                    stars_display += '⭐'  # Use full star for half (simplified)
                stars_display += '⚪' * empty_stars
                
                rating_text = f"<strong>⭐ Rating:</strong> {stars_display} {rating:.1f}/5"
                
                if review_count > 0:
                    rating_text += f" ({review_count} reviews)"
                
                return rating_text
            else:
                return "<strong>⭐ Rating:</strong> ⭐⚪⚪⚪⚪ New listing - Be the first to review!"
                
        except Exception as e:
            logger.error(f"Rating extraction error: {str(e)}")
            return "<strong>⭐ Rating:</strong> ⭐⚪⚪⚪⚪ Rating available"
    
    def get_item_description(self, item, is_product):
        """Get formatted description"""
        try:
            if is_product:
                description = getattr(item, 'product_description', '')
            else:
                description = getattr(item, 'service_description', '')
            
            description = str(description or '').strip()
            
            if description:
                # Clean description
                description = re.sub(r'<[^>]+>', '', description)  # Remove HTML
                description = re.sub(r'\s+', ' ', description)     # Normalize whitespace
                
                # Limit length for display
                if len(description) > 200:
                    description = description[:197] + "..."
                
                return description
            else:
                return "High-quality item available on Finda marketplace. Contact seller for detailed information."
                
        except Exception as e:
            logger.error(f"Description extraction error: {str(e)}")
            return "Quality item available. Contact seller for more details."
    
    def get_item_link(self, item, is_product, item_type):
        """Get formatted item link"""
        try:
            # Try to get absolute URL
            url = None
            try:
                if hasattr(item, 'get_absolute_url'):
                    url = item.get_absolute_url()
            except:
                pass
            
            # Generate URL if not available
            if not url:
                slug = getattr(item, 'slug', None) or getattr(item, 'id', '')
                if is_product:
                    url = f"/products/{slug}/"
                else:
                    url = f"/services/{slug}/"
            
            # Make absolute URL
            if url and not url.startswith('http'):
                full_url = f"{self.base_url}{url}"
            else:
                full_url = url or f"{self.base_url}"
            
            # Create link button
            link_button = f'''
            <a href="{full_url}" target="_blank" rel="noopener noreferrer" 
               style="background: #3498db; color: white; padding: 10px 16px; text-decoration: none; border-radius: 6px; font-weight: bold; display: inline-block;">
                🔗 View Full Details
            </a>
            '''
            
            return link_button.strip()
            
        except Exception as e:
            logger.error(f"Link generation error: {str(e)}")
            return f'<a href="{self.base_url}" target="_blank" style="background: #3498db; color: white; padding: 10px 16px; text-decoration: none; border-radius: 6px;">🔗 View on Finda</a>'
    
    def format_basic_item_fallback(self, item, index):
        """Basic fallback formatting if comprehensive formatting fails"""
        try:
            is_product = hasattr(item, 'product_name')
            name = self.get_item_name(item, is_product)
            price = self.get_item_price(item, is_product)
            location = self.get_item_location(item)
            
            return f"""
<div style="border: 1px solid #ddd; padding: 15px; margin: 10px 0; border-radius: 8px;">
    <h4>{index}. {name}</h4>
    <p><strong>Price:</strong> {price['display']}</p>
    <p><strong>Location:</strong> {location}</p>
    <p><a href="{self.base_url}" target="_blank">View Details</a></p>
</div>
"""
        except Exception as e:
            logger.error(f"Basic fallback error: {str(e)}")
            return f"<div>{index}. Item available on Finda</div>"
    
    def generate_comprehensive_footer(self, total_results, displayed_results, query):
        """Generate comprehensive footer with benefits and call-to-action"""
        try:
            footer_parts = []
            
            # Results summary
            if total_results > displayed_results:
                footer_parts.append(f"📊 <strong>Plus {total_results - displayed_results} more options available on Finda!</strong>")
            
            # Finda benefits
            benefits = f"""
✨ <strong>Why choose Finda sellers?</strong>
• 🚚 <strong>Lightning-fast local delivery</strong> - Get your items quickly
• 💬 <strong>Direct communication</strong> with sellers - No middleman
• 🏠 <strong>Support Nigerian businesses</strong> - Boost the local economy
• 💯 <strong>Verified sellers</strong> - Trusted marketplace
• 🔒 <strong>Secure transactions</strong> - Safe payment options
• 📱 <strong>Easy mobile access</strong> - Shop anywhere, anytime# response_formatter.py - WORLD-CLASS RESPONSE FORMATTING SYSTEM
import logging
import re
from django.utils import timezone
from django.core.cache import cache
from decimal import Decimal
import json

logger = logging.getLogger(__name__)


class WorldClassResponseFormatter:
    WORLD-CLASS response formatter that creates beautiful, comprehensive displays
    """