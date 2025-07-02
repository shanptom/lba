import streamlit as st
import pandas as pd
import requests
from urllib.parse import quote_plus
import time
import re
from bs4 import BeautifulSoup
import json
import fitz  # PyMuPDF for PDF reading
import openai
import google.generativeai as genai

# ==== CONFIGURATION ====
USE_GOOGLE_DIRECT = True  # Set False to use OpenRouter

# API Keys
if USE_GOOGLE_DIRECT:
    genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
else:
    openai.api_key = st.secrets["OPENROUTER_API_KEY"]
    openai.api_base = "https://openrouter.ai/api/v1"

# ==== SESSION STATE ====
if 'materials_with_links' not in st.session_state:
    st.session_state.materials_with_links = None
if 'search_completed' not in st.session_state:
    st.session_state.search_completed = False
if 'extracted_materials' not in st.session_state:
    st.session_state.extracted_materials = None

st.set_page_config(page_title="Lab Protocol Shopper", layout="wide")
st.title("📊 ProtoCart")
st.markdown("*Automatically extract materials from your protocol and find direct product links for easy purchasing*")

uploaded_file = st.file_uploader("Upload your lab protocol (TXT or PDF)", type=["txt", "pdf"])

vendor_site = st.selectbox(
    "Select your preferred vendor:",
    ["fishersci.com", "sigmaaldrich.com", "thermofisher.com"],
    help="Choose your preferred vendor for product links"
)

@st.cache_data
def extract_text(file):
    if file.type == "text/plain":
        return file.read().decode("utf-8")
    elif file.type == "application/pdf":
        pdf_reader = fitz.open(stream=file.read(), filetype="pdf")
        text = ""
        for page in pdf_reader:
            text += page.get_text()
        return text
    else:
        st.error("Unsupported file type.")
        return ""

def get_product_links(query, vendor, max_results=3):
    """Attempt to get actual product links by parsing search results"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }

    try:
        if vendor == "fishersci.com":
            search_url = f"https://www.fishersci.com/us/en/catalog/search/products?keyword={quote_plus(query)}"
            response = requests.get(search_url, headers=headers, timeout=10)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                product_links = []
                links = soup.find_all('a', href=True)
                for link in links:
                    href = link.get('href')
                    if href and '/shop/products/' in href:
                        full_url = href if href.startswith('http') else f"https://www.fishersci.com{href}"
                        product_links.append(full_url)
                        if len(product_links) >= max_results:
                            break
                return product_links if product_links else [search_url]

        elif vendor == "sigmaaldrich.com":
            search_url = f"https://www.sigmaaldrich.com/US/en/search/{quote_plus(query)}"
            response = requests.get(search_url, headers=headers, timeout=10)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                product_links = []
                links = soup.find_all('a', href=True)
                for link in links:
                    href = link.get('href')
                    if href and '/product/' in href:
                        full_url = href if href.startswith('http') else f"https://www.sigmaaldrich.com{href}"
                        product_links.append(full_url)
                        if len(product_links) >= max_results:
                            break
                return product_links if product_links else [search_url]

        elif vendor == "thermofisher.com":
            search_url = f"https://www.thermofisher.com/search/results?query={quote_plus(query)}"
            response = requests.get(search_url, headers=headers, timeout=10)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                product_links = []
                links = soup.find_all('a', href=True)
                for link in links:
                    href = link.get('href')
                    if href and ('/order/' in href or '/product/' in href):
                        full_url = href if href.startswith('http') else f"https://www.thermofisher.com{href}"
                        product_links.append(full_url)
                        if len(product_links) >= max_results:
                            break
                return product_links if product_links else [search_url]

    except Exception as e:
        print(f"Error fetching products for {query}: {e}")
        return [search_url]

    return ["Search failed"]

def search_all_products(materials, vendor):
    """Search for all materials and get product links"""
    results = []
    progress_bar = st.progress(0)
    status_text = st.empty()

    for i, material in enumerate(materials):
        status_text.text(f"Searching for: {material['name']}")
        links = get_product_links(material['name'], vendor)
        material['product_links'] = links
        material['primary_link'] = links[0] if links else "Not found"
        results.append(material)
        progress_bar.progress((i + 1) / len(materials))
        time.sleep(0.5)

    progress_bar.empty()
    status_text.empty()
    return results


def get_chemicals_from_protocol(text):
    system_prompt = """You are a laboratory purchasing assistant. Extract all materials that need to be purchased for this protocol.

    Focus on:
    - Chemicals and reagents (buffers, enzymes, antibodies, etc.)
    - Consumables (tubes, tips, plates, etc.)
    - Small equipment/tools that are consumable

    For each item, provide:
    - Exact name as mentioned in protocol
    - Type (chemical/reagent/consumable/equipment)
    - Key specifications (concentration, volume, size, grade)
    - Catalog hints (brand names, common aliases)

    Respond ONLY with valid JSON:
    [
      {
        "name": "Tris-HCl buffer",
        "type": "chemical",
        "specifications": "1M, pH 8.0, molecular biology grade",
        "catalog_hints": "Tris buffer, TRIS-HCl, Tris hydrochloride"
      }
    ]

    Do not include basic lab equipment like pipettes, centrifuges, or items clearly already available."""

    try:
        if USE_GOOGLE_DIRECT:
            model = genai.GenerativeModel("gemini-2.0-flash")
            response = model.generate_content(
                f"{system_prompt}\n\nExtract purchasable materials from this protocol:\n\n{text}"
)
            response_text = response.text.strip()
        else:
            response = openai.ChatCompletion.create(
                model="google/gemini-2.0-flash",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Extract purchasable materials from this protocol:\n\n{text}"}
                ],
                temperature=0,
                max_tokens=2000
            )
            response_text = response.choices[0].message["content"].strip()

        if response_text.startswith("```json"):
            response_text = response_text.replace("```json", "").replace("```", "").strip()
        elif response_text.startswith("```"):
            response_text = response_text.replace("```", "").strip()

        try:
            materials = json.loads(response_text)
            if isinstance(materials, list) and all(isinstance(item, dict) and 'name' in item for item in materials):
                return materials
            else:
                st.error("Invalid materials format returned")
                return []
        except json.JSONDecodeError as e:
            st.error(f"Could not parse materials list: {e}")
            return []

    except Exception as e:
        st.error(f"Error calling Gemini model: {str(e)}")
        return []


def create_shopping_interface(materials_with_links, vendor):
    """Create an interface that mimics the shopping experience"""
    st.markdown("### 🛒 Your Shopping Assistant")
    st.markdown(f"**Vendor:** {vendor}")
    
    # Summary
    total_items = len(materials_with_links)
    found_links = sum(1 for item in materials_with_links if item.get('primary_link') and 'search' not in item['primary_link'].lower())
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Items", total_items)
    with col2:
        st.metric("Direct Links Found", found_links)
    with col3:
        st.metric("Success Rate", f"{(found_links/total_items)*100:.0f}%" if total_items > 0 else "0%")
    
    st.markdown("---")
    
    # Shopping checklist
    st.markdown("### Shopping Checklist")
    st.markdown("*Click links to open products in new tabs, then add to cart*")
    
    # Add clear all button
    col1, col2 = st.columns([1, 4])
    with col1:
        if st.button("🗑️ Clear Results", type="secondary"):
            st.session_state.search_completed = False
            st.session_state.materials_with_links = None
            st.rerun()
    
    st.markdown("---")
    
    for i, item in enumerate(materials_with_links, 1):
        with st.container():
            col1, col2 = st.columns([3, 1])
            
            with col1:
                # Item details
                st.markdown(f"**{i}. {item['name']}**")
                st.markdown(f"*{item.get('type', 'Unknown').title()}*")
                
                if item.get('specifications'):
                    st.markdown(f"📋 **Specs:** {item['specifications']}")
                
                if item.get('catalog_hints'):
                    st.markdown(f"🔍 **Search terms:** {item['catalog_hints']}")
            
            with col2:
                # Action buttons - use markdown links instead of buttons to prevent rerun
                primary_link = item.get('primary_link', '')
                if primary_link and primary_link != "Not found":
                    # Determine if it's a direct product link or search
                    is_direct = not any(term in primary_link.lower() for term in ['search', 'results', 'keyword'])
                    
                    if is_direct:
                        st.markdown(f"🛒 **[Add to Cart]({primary_link})**", unsafe_allow_html=True)
                    else:
                        st.markdown(f"🔍 **[Search Product]({primary_link})**", unsafe_allow_html=True)
                    
                    # Show additional links if available
                    additional_links = item.get('product_links', [])[1:]
                    if additional_links:
                        st.markdown("**More options:**")
                        for j, link in enumerate(additional_links):
                            st.markdown(f"[Option {j+2}]({link})")
                else:
                    st.warning("❌ Not found")
                    manual_search = f"https://www.{vendor}/search?q={quote_plus(item['name'])}"
                    st.markdown(f"[Manual Search]({manual_search})")
            
            # Checkbox for tracking - Initialize session state only if not exists
            checkbox_key = f"purchased_{i}"
            if checkbox_key not in st.session_state:
                st.session_state[checkbox_key] = False
            
            # Create checkbox - it will automatically update session state
            st.checkbox(f"✅ Added to cart", key=checkbox_key)
            
            st.markdown("---")

# Main app logic
if uploaded_file:
    protocol_text = extract_text(uploaded_file)
    
    # Protocol preview
    with st.expander("📄 Protocol Preview"):
        st.text_area("", protocol_text[:2000] + "..." if len(protocol_text) > 2000 else protocol_text, height=150)
    
    # Extract materials (only if not already done)
    if st.session_state.extracted_materials is None:
        with st.spinner("🤖 Analyzing protocol with Claude..."):
            materials = get_chemicals_from_protocol(protocol_text)
            st.session_state.extracted_materials = materials
    else:
        materials = st.session_state.extracted_materials
    
    if materials:
        st.success(f"✅ Found {len(materials)} items to purchase")
        
        # Show extracted materials
        with st.expander("📋 Extracted Materials"):
            for i, material in enumerate(materials, 1):
                st.write(f"**{i}. {material['name']}** ({material.get('type', 'Unknown')})")
                if material.get('specifications'):
                    st.write(f"   📋 {material['specifications']}")
        
        # Search for products
        if not st.session_state.search_completed:
            if st.button("🔍 Find Products", type="primary"):
                with st.spinner(f"🛒 Searching {vendor_site} for products..."):
                    materials_with_links = search_all_products(materials, vendor_site)
                    st.session_state.materials_with_links = materials_with_links
                    st.session_state.search_completed = True
                st.rerun()
        
        # Show shopping interface if search is completed
        if st.session_state.search_completed and st.session_state.materials_with_links:
            create_shopping_interface(st.session_state.materials_with_links, vendor_site)
            
            # Download options
            st.markdown("### 📥 Export Options")
            
            # Create CSV data
            csv_data = []
            for i, item in enumerate(st.session_state.materials_with_links, 1):
                checkbox_key = f"purchased_{i}"
                purchased_status = "Yes" if st.session_state.get(checkbox_key, False) else "No"
                
                csv_data.append({
                    'Item': item['name'],
                    'Type': item.get('type', ''),
                    'Specifications': item.get('specifications', ''),
                    'Primary_Link': item.get('primary_link', ''),
                    'All_Links': ' | '.join(item.get('product_links', [])),
                    'Added_to_Cart': purchased_status
                })
            
            df = pd.DataFrame(csv_data)
            st.download_button(
                "📥 Download Shopping List (CSV)",
                df.to_csv(index=False),
                file_name=f"protocol_shopping_list_{vendor_site.replace('.', '_')}.csv",
                mime="text/csv"
            )
    else:
        st.warning("⚠️ No purchasable materials found. Please check your protocol format.")

else:
    # Reset session state when no file is uploaded
    st.session_state.materials_with_links = None
    st.session_state.search_completed = False
    st.session_state.extracted_materials = None
    
    # Landing page
    st.markdown("### 🧬 How It Works")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("**1. Upload Protocol**")
        st.markdown("Upload your lab protocol as a text file")
    
    with col2:
        st.markdown("**2. AI Extraction**")
        st.markdown("Claude identifies all materials to purchase")
    
    with col3:
        st.markdown("**3. Smart Shopping**")
        st.markdown("Get direct product links for easy cart additions")
    
    st.markdown("### 📝 Example Protocol Format")
    st.code("""
## DNA Extraction Protocol
**Step 1: Tissue Homogenization**
- Weigh 100 mg of fresh Arabidopsis leaves and place in a 2 mL microcentrifuge tube.
- Add 500 µL of Lysis Buffer(CTAB-based, containing 2% CTAB, 100 mM Tris-HCl, 20 mM EDTA, 1.4 M NaCl) and 10 µL of RNase A (10 mg/mL).
- Vortex vigorously for 30 sec until the tissue is fully disrupted.

**Step 2: Incubation & Protein Removal**
- Incubate the mixture at 65°C for 10 min in a water bath.
- Add 500 µL of Chloroform:Isoamyl Alcohol (24:1) and mix by inversion for 5 min.
- Centrifuge at 12,000 × *g* for 5 min. Transfer the aqueous (top) phase to a new tube.

**Step 3: DNA Precipitation**
- Add 0.7 volumes of Isopropanol and mix gently. Incubate at -20°C for 30 min.
- Centrifuge at 12,000 × *g* for 10 min to pellet DNA. Discard the supernatant.

**Step 4: Washing & Elution**
- Wash the pellet with 500 µL of 70% Ethanol, then centrifuge at 12,000 × *g* for 2 min. Air-dry for 5 min.
- Resuspend the DNA in 50 µL of Elution Buffer (10 mM Tris-HCl, pH 8.5) and transfer to a DNA spin column.
- Centrifuge at 12,000 × *g* for 1 min to collect purified DNA.

**Step 5: Quantification**
- Measure DNA concentration using a Nanodrop Spectrophotometer at 260 nm.
- Store DNA at -20°C for long-term use.
    """, language="text")

# Sidebar
with st.sidebar:
    st.markdown("### 💡 Pro Tips")
    st.markdown("""
    **For best results:**
    - Include specific product names/brands
    - Mention concentrations and grades
    - Use standard lab terminology
    - List consumables separately
    """)
    
    st.markdown("### 🔧 Troubleshooting")
    st.markdown("""
    **If links don't work:**
    - Try different search terms
    - Check vendor availability
    - Use manual search fallback
    - Contact vendor directly
    """)
    
    st.markdown("### ⚠️ Disclaimer")
    st.markdown("""
    This tool provides search assistance only. 
    Always verify:
    - Product specifications
    - Pricing and availability
    - Shipping requirements
    """)
