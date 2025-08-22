#!/usr/bin/env python3
"""
Simple test script to verify CDSE credentials are working
"""

import requests
import os

def test_cdse_authentication():
    """Test CDSE authentication with your credentials"""
    
    print("🔑 Testing CDSE Authentication")
    print("=" * 40)
    
    # Get credentials
    username = os.getenv('CDSE_USERNAME')
    password = os.getenv('CDSE_PASSWORD')
    
    # Check if credentials are provided
    if not username or not password:
        print("❌ Credentials not found!")
        print("\nPlease set your credentials:")
        print("export CDSE_USERNAME='your_email@example.com'")
        print("export CDSE_PASSWORD='your_password'")
        print("\nOr run this script with:")
        print("CDSE_USERNAME='your_email' CDSE_PASSWORD='your_password' python test_cdse_credentials.py")
        return False
    
    print(f"📧 Username: {username}")
    print(f"🔐 Password: {'*' * len(password)}")
    print()
    
    try:
        # CDSE token endpoint
        token_url = "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token"
        
        print("🌐 Connecting to CDSE...")
        
        # Request token
        data = {
            'client_id': 'cdse-public',
            'grant_type': 'password',
            'username': username,
            'password': password
        }
        
        response = requests.post(token_url, data=data, timeout=30)
        
        print(f"📡 Response status: {response.status_code}")
        
        if response.status_code == 200:
            token_data = response.json()
            
            print("✅ Authentication SUCCESS!")
            print(f"🎫 Token type: {token_data.get('token_type', 'unknown')}")
            print(f"⏰ Token expires in: {token_data.get('expires_in', 'unknown')} seconds")
            
            # Test a simple API call
            print("\n🧪 Testing API access...")
            test_api_access(token_data['access_token'])
            
            return True
            
        elif response.status_code == 401:
            print("❌ Authentication FAILED!")
            print("🔍 Possible issues:")
            print("   • Wrong username or password")
            print("   • Account not activated (check your email)")
            print("   • Account locked or suspended")
            print(f"\n📝 Server response: {response.text}")
            
        elif response.status_code == 400:
            print("❌ Bad request!")
            print("🔍 Possible issues:")
            print("   • Invalid request format")
            print("   • Missing required parameters")
            print(f"\n📝 Server response: {response.text}")
            
        else:
            print(f"❌ Unexpected error: HTTP {response.status_code}")
            print(f"📝 Server response: {response.text}")
        
        return False
        
    except requests.exceptions.Timeout:
        print("❌ Connection timeout!")
        print("🔍 Check your internet connection")
        return False
        
    except requests.exceptions.ConnectionError:
        print("❌ Connection error!")
        print("🔍 Cannot reach CDSE servers")
        return False
        
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False

def test_api_access(token):
    """Test a simple API call with the token"""
    try:
        # Simple test: get collections info
        api_url = "https://catalogue.dataspace.copernicus.eu/odata/v1/Collections"
        
        headers = {
            'Authorization': f'Bearer {token}'
        }
        
        response = requests.get(api_url, headers=headers, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            collections = data.get('value', [])
            
            print(f"✅ API access SUCCESS!")
            print(f"📚 Found {len(collections)} collections")
            
            # Look for CLMS collection
            clms_found = False
            for collection in collections:
                if collection.get('Name') == 'CLMS':
                    clms_found = True
                    print(f"🌊 CLMS collection found: {collection.get('Description', 'No description')}")
                    break
            
            if not clms_found:
                print("⚠️  CLMS collection not found in available collections")
                print("📋 Available collections:")
                for collection in collections[:5]:  # Show first 5
                    print(f"   • {collection.get('Name', 'Unknown')}")
            
        else:
            print(f"❌ API test failed: HTTP {response.status_code}")
            print(f"📝 Response: {response.text}")
            
    except Exception as e:
        print(f"❌ API test error: {e}")

def interactive_credential_test():
    """Interactive credential testing"""
    print("🧪 Interactive Credential Test")
    print("=" * 40)
    
    # Get credentials interactively if not in environment
    username = os.getenv('CDSE_USERNAME')
    password = os.getenv('CDSE_PASSWORD')
    
    if not username:
        username = input("📧 Enter your CDSE username (email): ").strip()
    
    if not password:
        import getpass
        password = getpass.getpass("🔐 Enter your CDSE password: ")
    
    # Set environment variables temporarily
    os.environ['CDSE_USERNAME'] = username
    os.environ['CDSE_PASSWORD'] = password
    
    # Run test
    return test_cdse_authentication()

def main():
    """Main function"""
    print("🌊 CDSE Credential Test")
    print("=" * 50)
    print()
    
    # Try environment variables first
    if os.getenv('CDSE_USERNAME') and os.getenv('CDSE_PASSWORD'):
        success = test_cdse_authentication()
    else:
        print("💡 No environment variables found. Let's test interactively!")
        print()
        success = interactive_credential_test()
    
    print("\n" + "=" * 50)
    if success:
        print("🎉 Credentials working! You're ready to download Water Bodies data!")
    else:
        print("🔧 Fix the issues above and try again.")
        print("\n💡 Quick setup reminder:")
        print("1. Register at: https://dataspace.copernicus.eu/")
        print("2. Check your email for activation")
        print("3. Set credentials: export CDSE_USERNAME='your_email'")

if __name__ == "__main__":
    main()