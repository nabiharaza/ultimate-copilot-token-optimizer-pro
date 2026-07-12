"""
Test script to verify compression quality vs Headroom
"""
import sys
from TrimP.compression.advanced import (
    CodeContextTrimmer,
    ConversationCompressor,
    JSONMinimizer,
    LogExtractor,
    LLMLinguaLite,
    UniversalOptimizer,
)

# Test samples
CODE_SAMPLE = '''
def calculate_total(items):
    """Calculate the total price of items"""
    total = 0
    for item in items:
        if item.get('price'):
            total += item['price'] * item.get('quantity', 1)
    return total

def process_order(order_id):
    """Process an order"""
    order = get_order(order_id)
    if order:
        total = calculate_total(order['items'])
        charge_customer(order['customer_id'], total)
        send_confirmation(order['email'])
    return True
'''

JSON_SAMPLE = '''{
  "users": [
    {"id": 1, "name": "Alice", "email": "alice@example.com", "age": 30},
    {"id": 2, "name": "Bob", "email": "bob@example.com", "age": 25},
    {"id": 3, "name": "Charlie", "email": "charlie@example.com", "age": 35}
  ],
  "metadata": {
    "total_count": 3,
    "page": 1,
    "per_page": 10,
    "timestamp": "2024-01-15T10:30:00Z"
  }
}'''

LOG_SAMPLE = '''
[2024-01-15 10:30:00] INFO: Application started
[2024-01-15 10:30:01] INFO: Connection established
[2024-01-15 10:30:02] INFO: Database connected
[2024-01-15 10:30:03] INFO: Cache initialized
[2024-01-15 10:30:04] ERROR: Failed to load config file
[2024-01-15 10:30:05] ERROR: Retrying with defaults
[2024-01-15 10:30:06] INFO: Server listening on port 8080
'''

CONVERSATION_SAMPLE = '''
User: How do I deploy a Kubernetes cluster?
Assistant: To deploy a Kubernetes cluster, you have several options...
User: What about using EKS on AWS?
Assistant: Amazon EKS is a great choice for managed Kubernetes...
User: Can you show me the terraform code?
Assistant: Sure, here's an example terraform configuration...
'''

def test_compressor(name, compressor, sample):
    """Test a single compressor"""
    print(f"\n{'='*60}")
    print(f"Testing: {name}")
    print(f"{'='*60}")
    
    try:
        result = compressor.compress(sample)
        
        # Handle tuple return (text, metadata)
        if isinstance(result, tuple):
            compressed, metadata = result
        else:
            compressed = result
            metadata = {}
        
        original_len = len(sample)
        compressed_len = len(compressed)
        savings_pct = ((original_len - compressed_len) / original_len * 100)
        
        print(f"Original length:    {original_len:,} chars")
        print(f"Compressed length:  {compressed_len:,} chars")
        print(f"Savings:            {savings_pct:.1f}%")
        
        if metadata:
            print(f"Metadata:           {metadata}")
        
        print(f"\nOriginal (first 100 chars):\n{sample[:100]}...")
        print(f"\nCompressed (first 100 chars):\n{compressed[:100]}...")
        
        return savings_pct
        
    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 0

def main():
    """Run all compression tests"""
    print("🧪 TRIMP Compression Quality Test")
    print("=" * 60)
    
    results = {}
    
    # Test Code Compression
    results['code'] = test_compressor(
        "Code Compression",
        CodeContextTrimmer(),
        CODE_SAMPLE
    )
    
    # Test JSON Compression
    results['json'] = test_compressor(
        "JSON Compression",
        JSONMinimizer(),
        JSON_SAMPLE
    )
    
    # Test Log Compression
    results['log'] = test_compressor(
        "Log Compression",
        LogExtractor(),
        LOG_SAMPLE
    )
    
    # Test Conversation Compression
    results['conversation'] = test_compressor(
        "Conversation Compression",
        ConversationCompressor(),
        CONVERSATION_SAMPLE
    )
    
    # Test Universal (should route to appropriate compressor)
    results['universal'] = test_compressor(
        "Universal Optimizer",
        UniversalOptimizer(),
        CODE_SAMPLE
    )
    
    # Test Lingua Lite
    results['lingua'] = test_compressor(
        "LLMLingua Lite",
        LLMLinguaLite(),
        "This is a very long piece of text with lots of words that could be compressed by removing low-information tokens and keeping only the most important content for understanding."
    )
    
    # Summary
    print(f"\n{'='*60}")
    print("📊 RESULTS SUMMARY")
    print(f"{'='*60}")
    
    for name, savings in results.items():
        status = "✅" if savings > 30 else "⚠️" if savings > 10 else "❌"
        print(f"{status} {name:20s}: {savings:5.1f}% savings")
    
    avg_savings = sum(results.values()) / len(results)
    print(f"\n📈 Average Savings: {avg_savings:.1f}%")
    
    # Target comparison
    print(f"\n🎯 Headroom Target Comparison:")
    targets = {
        'code': 50,
        'json': 65,
        'log': 60,
        'conversation': 55,
        'universal': 50,
        'lingua': 40
    }
    
    for name, target in targets.items():
        actual = results.get(name, 0)
        diff = actual - target
        status = "✅" if diff >= 0 else "❌"
        print(f"{status} {name:20s}: {actual:5.1f}% (target: {target}%, diff: {diff:+.1f}%)")

if __name__ == "__main__":
    main()
