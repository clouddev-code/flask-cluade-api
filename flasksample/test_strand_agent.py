#!/usr/bin/env python3

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_strand_agent_import():
    """Test that Strand Agent client can be imported successfully"""
    try:
        from modules.strand_agent_client import agent, process_chat_sync
        print('✅ Strand Agent client imported successfully')
        print(f'Agent name: {agent.name}')
        print(f'Agent description: {agent.description}')
        print('✅ Agent initialized successfully')
        return True
    except ImportError as e:
        print(f'❌ Import error: {e}')
        return False
    except Exception as e:
        print(f'❌ Other error: {e}')
        return False

def test_basic_functionality():
    """Test basic functionality without making actual API calls"""
    try:
        from modules.strand_agent_client import text_chat_tool
        print('✅ Text chat tool imported successfully')
        return True
    except Exception as e:
        print(f'❌ Error testing basic functionality: {e}')
        return False

if __name__ == "__main__":
    print("Testing Strand Agent Phase 1 Implementation...")
    print("=" * 50)
    
    success = True
    success &= test_strand_agent_import()
    success &= test_basic_functionality()
    
    print("=" * 50)
    if success:
        print("✅ All tests passed!")
    else:
        print("❌ Some tests failed!")
    
    sys.exit(0 if success else 1)
