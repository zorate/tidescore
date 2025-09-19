from PIL import Image, ImageDraw, ImageFont
import os
import math

def create_rounded_rectangle(width, height, radius, fill_color):
    """Create a rounded rectangle image"""
    img = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # Draw rounded rectangle
    draw.rounded_rectangle([0, 0, width, height], radius=radius, fill=fill_color)
    
    return img

def create_tidescore_logo(size, is_favicon=True):
    """Create a TideScore logo with wave and T design"""
    # Colors - Modern blue gradient
    if is_favicon:
        bg_color = (66, 133, 244, 255)  # Solid blue for favicon
    else:
        # Gradient background for larger logos
        bg_color = (52, 152, 219, 255)  # Darker blue
    
    white_color = (255, 255, 255, 255)
    accent_color = (41, 128, 185, 255)  # Darker blue accent
    
    # Create background
    corner_radius = size // 6
    img = create_rounded_rectangle(size, size, corner_radius, bg_color)
    draw = ImageDraw.Draw(img)
    
    # Calculate dimensions
    margin = size // 10
    
    if is_favicon:
        # Simplified design for favicon
        # Draw the T
        t_width = size // 3
        t_height = size // 12
        t_stem_width = size // 8
        
        # Position for the T
        t_x = (size - t_width) // 2
        t_y = margin + size // 8
        
        # Draw the horizontal bar of the T
        draw.rectangle([t_x, t_y, t_x + t_width, t_y + t_height], fill=white_color)
        
        # Draw the vertical stem of the T
        stem_x = (size - t_stem_width) // 2
        stem_y = t_y
        stem_height = size // 2.5
        draw.rectangle([stem_x, stem_y, stem_x + t_stem_width, stem_y + stem_height], fill=white_color)
        
        # Draw simplified wave
        wave_height = size // 4
        wave_width = size // 1.5
        wave_x = (size - wave_width) // 2
        wave_y = size - margin - wave_height
        
        # Create wave points
        wave_points = []
        num_points = 20
        
        for i in range(num_points + 1):
            x = wave_x + (wave_width * i / num_points)
            # Sine wave pattern
            y_offset = (wave_height / 3) * math.sin(2 * math.pi * i / num_points)
            y = wave_y + y_offset + wave_height / 2
            wave_points.append((x, y))
        
        # Close the wave shape
        wave_points.append((wave_x + wave_width, size))
        wave_points.append((wave_x, size))
        
        if len(wave_points) > 2:
            draw.polygon(wave_points, fill=white_color)
            
    else:
        # Enhanced design for larger logos
        # Draw stylized T with gradient
        t_width = size // 2
        t_height = size // 15
        t_stem_width = size // 10
        
        # Position for the T
        t_x = (size - t_width) // 2
        t_y = margin + size // 6
        
        # Draw the horizontal bar with slight gradient
        for i in range(t_height):
            alpha = 255 - (i * 20 // t_height)
            draw.rectangle([t_x, t_y + i, t_x + t_width, t_y + i + 1], 
                          fill=(255, 255, 255, alpha))
        
        # Draw the vertical stem
        stem_x = (size - t_stem_width) // 2
        stem_y = t_y
        stem_height = size // 2
        
        for i in range(t_stem_width):
            alpha = 255 - (i * 20 // t_stem_width)
            draw.rectangle([stem_x + i, stem_y, stem_x + i + 1, stem_y + stem_height], 
                          fill=(255, 255, 255, alpha))
        
        # Draw more detailed wave
        wave_height = size // 3
        wave_width = size
        wave_x = 0
        wave_y = size - margin - wave_height
        
        # Create double wave pattern
        for wave_num in range(2):
            wave_points = []
            num_points = 30
            
            for i in range(num_points + 1):
                x = wave_x + (wave_width * i / num_points)
                # Double sine wave for more complex pattern
                y_offset = (wave_height / 4) * math.sin(4 * math.pi * i / num_points + wave_num * math.pi/2)
                y = wave_y + y_offset + wave_height / 2
                wave_points.append((x, y))
            
            # Close the wave shape
            wave_points.append((wave_width, size))
            wave_points.append((0, size))
            
            if len(wave_points) > 2:
                # Use slightly transparent white for waves
                wave_color = (255, 255, 255, 200 if wave_num == 0 else 150)
                draw.polygon(wave_points, fill=wave_color)
    
    return img

def create_app_icon(size=512):
    """Create a full app icon with text"""
    # Create base logo
    img = create_tidescore_logo(size, is_favicon=False)
    draw = ImageDraw.Draw(img)
    
    # Try to use a font if available
    try:
        # Try different font paths
        font_paths = [
            '/System/Library/Fonts/Arial.ttf',  # macOS
            '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',  # Linux
            'C:/Windows/Fonts/arialbd.ttf',  # Windows
            'arialbd.ttf'
        ]
        
        font = None
        for path in font_paths:
            try:
                font = ImageFont.truetype(path, size // 8)
                break
            except:
                continue
        
        if font is None:
            # Use default font if no system fonts found
            font = ImageFont.load_default()
        
        # Add text below the logo
        text = "TideScore"
        text_width = draw.textlength(text, font=font)
        text_x = (size - text_width) // 2
        text_y = size - size // 6
        
        # Draw text with shadow effect
        shadow_color = (0, 0, 0, 100)
        text_color = (255, 255, 255, 255)
        
        # Shadow
        draw.text((text_x + 2, text_y + 2), text, fill=shadow_color, font=font)
        # Main text
        draw.text((text_x, text_y), text, fill=text_color, font=font)
        
    except Exception as e:
        print(f"Could not load font: {e}")
        # Continue without text
    
    return img

def create_pwa_icons():
    """Create all necessary PWA icons"""
    sizes = [
        (16, 'static/favicon-16x16.png'),
        (32, 'static/favicon-32x32.png'),
        (48, 'static/favicon-48x48.png'),
        (72, 'static/icon-72x72.png'),
        (96, 'static/icon-96x96.png'),
        (128, 'static/icon-128x128.png'),
        (144, 'static/icon-144x144.png'),
        (152, 'static/icon-152x152.png'),
        (192, 'static/icon-192x192.png'),
        (384, 'static/icon-384x384.png'),
        (512, 'static/icon-512x512.png')
    ]
    
    # Also create app icons
    app_icon_sizes = [
        (180, 'static/apple-touch-icon.png'),
        (192, 'static/android-chrome-192x192.png'),
        (512, 'static/android-chrome-512x512.png')
    ]
    
    all_sizes = sizes + app_icon_sizes
    
    for size, filename in all_sizes:
        print(f"Generating {filename} ({size}x{size})...")
        
        # Use simplified design for small icons, detailed for larger ones
        is_favicon = size <= 48
        icon = create_tidescore_logo(size, is_favicon=is_favicon)
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        icon.save(filename, 'PNG')
        print(f"✓ Saved {filename}")

def create_logo_with_text(width=800, height=400):
    """Create a horizontal logo with text for website headers"""
    # Create canvas
    img = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # Create icon part
    icon_size = min(width // 2, height)
    icon = create_tidescore_logo(icon_size, is_favicon=False)
    
    # Paste icon
    img.paste(icon, (50, (height - icon_size) // 2), icon)
    
    # Add text
    try:
        font_size = height // 3
        font_paths = [
            '/System/Library/Fonts/Arial.ttf',
            '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
            'C:/Windows/Fonts/arialbd.ttf',
            'arialbd.ttf'
        ]
        
        font = None
        for path in font_paths:
            try:
                font = ImageFont.truetype(path, font_size)
                break
            except:
                continue
        
        if font:
            text = "TideScore"
            text_width = draw.textlength(text, font=font)
            text_x = icon_size + 100
            text_y = (height - font_size) // 2
            
            # Gradient text effect
            for i in range(len(text)):
                char = text[i]
                char_width = draw.textlength(char, font=font)
                
                # Blue gradient from dark to light
                blue_value = 100 + (i * 155 // len(text))
                text_color = (0, blue_value, 255, 255)
                
                draw.text((text_x, text_y), char, fill=text_color, font=font)
                text_x += char_width
    except:
        # Fallback if font loading fails
        pass
    
    return img

def main():
    """Main function to generate all icons and logos"""
    print("🚀 Generating TideScore icons and logos...")
    
    # Create static directory if it doesn't exist
    os.makedirs('static', exist_ok=True)
    
    # Generate PWA icons
    print("\n📱 Generating PWA icons...")
    create_pwa_icons()
    
    # Generate app icon with text
    print("\n📲 Generating app icon...")
    app_icon = create_app_icon(512)
    app_icon.save('static/app-icon.png', 'PNG')
    print("✓ Saved static/app-icon.png")
    
    # Generate website logo
    print("\n🌐 Generating website logo...")
    website_logo = create_logo_with_text(800, 200)
    website_logo.save('static/website-logo.png', 'PNG')
    print("✓ Saved static/website-logo.png")
    
    # Generate square logo
    print("\n🔲 Generating square logo...")
    square_logo = create_tidescore_logo(400, is_favicon=False)
    square_logo.save('static/square-logo.png', 'PNG')
    print("✓ Saved static/square-logo.png")
    
    # Generate favicon.ico (multiple sizes in one file)
    print("\n🎯 Generating favicon.ico...")
    favicon_sizes = [16, 32, 48]
    favicons = []
    
    for size in favicon_sizes:
        favicon = create_tidescore_logo(size, is_favicon=True)
        favicons.append(favicon)
    
    # Save as .ico with multiple sizes
    favicons[0].save('static/favicon.ico', format='ICO', sizes=[(s, s) for s in favicon_sizes])
    print("✓ Saved static/favicon.ico")
    
    print("\n✅ All icons and logos generated successfully!")
    print("\n📁 Generated files:")
    print("  - PWA icons (multiple sizes)")
    print("  - App icon (static/app-icon.png)")
    print("  - Website logo (static/website-logo.png)")
    print("  - Square logo (static/square-logo.png)")
    print("  - Favicon (static/favicon.ico)")

if __name__ == "__main__":
    main()