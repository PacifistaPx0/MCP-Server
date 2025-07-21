import asyncio
import time
import subprocess
import sys
from mcp.client.sse import sse_client
from mcp.client.stdio import stdio_client, StdioServerParameters
import statistics
import httpx

class SpeedTest:
    def __init__(self):
        self.results = {}
    
    async def test_stdio(self, num_calls=50, data_size="large"):
        """Test stdio transport speed with configurable data size"""
        server_params = StdioServerParameters(
            command="uv",
            args=["run", "python", "server.py", "--transport", "stdio"]
        )
        
        # Generate test data based on size
        test_data = self.generate_test_data(data_size)
        times = []
        
        try:
            async with stdio_client(server_params) as (read_stream, write_stream):
                from mcp.client.session import ClientSession
                async with ClientSession(read_stream, write_stream) as session:
                    # Initialize the session
                    await session.initialize()
                    
                    # Warm up
                    await session.call_tool("add", {"numbers": [1, 2]})
                    
                    # Run tests
                    for i in range(num_calls):
                        start_time = time.perf_counter()
                        result = await session.call_tool("add", {"numbers": test_data})
                        end_time = time.perf_counter()
                        times.append(end_time - start_time)
                        if i % 10 == 0:  # Print progress every 10 calls
                            print(f"STDIO Call {i+1}/{num_calls}: {times[-1]:.4f}s")
        except Exception as e:
            print(f"STDIO test failed: {e}")
            return []
        
        return times
    
    async def test_sse(self, num_calls=50, data_size="large"):
        """Test SSE transport speed with configurable data size"""
        test_data = self.generate_test_data(data_size)
        times = []
        
        try:
            async with sse_client("http://localhost:8080/sse") as (read_stream, write_stream):
                from mcp.client.session import ClientSession
                async with ClientSession(read_stream, write_stream) as session:
                    # Initialize the session
                    await session.initialize()
                    
                    # Warm up
                    await session.call_tool("add", {"numbers": [1, 2]})
                    
                    # Run tests
                    for i in range(num_calls):
                        start_time = time.perf_counter()
                        result = await session.call_tool("add", {"numbers": test_data})
                        end_time = time.perf_counter()
                        times.append(end_time - start_time)
                        if i % 10 == 0:  # Print progress every 10 calls
                            print(f"SSE Call {i+1}/{num_calls}: {times[-1]:.4f}s")
        except Exception as e:
            print(f"SSE test failed: {e}")
            return []
        
        return times
    
    async def test_streamable_http(self, num_calls=50, data_size="large"):
        """Test Streamable HTTP transport speed with configurable data size"""
        test_data = self.generate_test_data(data_size)
        times = []
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                # Test basic connectivity first
                try:
                    response = await client.get("http://localhost:8050")
                    print(f"Server response status: {response.status_code}")
                except Exception as e:
                    print(f"Cannot connect to HTTP server: {e}")
                    return []
                
                # Run tests with direct HTTP calls
                for i in range(num_calls):
                    start_time = time.perf_counter()
                    
                    # Make HTTP request with larger data
                    response = await client.post(
                        "http://localhost:8050",
                        json={
                            "jsonrpc": "2.0",
                            "id": i,
                            "method": "tools/call",
                            "params": {
                                "name": "add",
                                "arguments": {"numbers": test_data}
                            }
                        },
                        headers={"Content-Type": "application/json"}
                    )
                    
                    end_time = time.perf_counter()
                    times.append(end_time - start_time)
                    if i % 10 == 0:  # Print progress every 10 calls
                        print(f"HTTP Call {i+1}/{num_calls}: {times[-1]:.4f}s (Status: {response.status_code})")
                    
        except Exception as e:
            print(f"Streamable HTTP test failed: {e}")
            return []
        
        return times
    
    def generate_test_data(self, size="large"):
        """Generate test data of different sizes"""
        if size == "small":
            return list(range(1, 11))  # 10 numbers
        elif size == "medium":
            return list(range(1, 101))  # 100 numbers
        elif size == "large":
            return list(range(1, 1001))  # 1000 numbers
        elif size == "huge":
            return list(range(1, 10001))  # 10,000 numbers
        elif size == "massive":
            return list(range(1, 100001))  # 100,000 numbers
        else:
            return list(range(1, 1001))  # Default to large
    
    def analyze_results(self, transport_name, times, data_size):
        """Analyze timing results with data size info"""
        if not times:
            print(f"\n{transport_name} ({data_size}): No data collected")
            return
        
        avg_time = statistics.mean(times)
        median_time = statistics.median(times)
        min_time = min(times)
        max_time = max(times)
        std_dev = statistics.stdev(times) if len(times) > 1 else 0
        
        print(f"\n{transport_name} Results ({data_size} data):")
        print(f"  Calls made: {len(times)}")
        print(f"  Average: {avg_time:.4f}s")
        print(f"  Median:  {median_time:.4f}s")
        print(f"  Min:     {min_time:.4f}s")
        print(f"  Max:     {max_time:.4f}s")
        print(f"  Std Dev: {std_dev:.4f}s")
        print(f"  Calls/sec: {1/avg_time:.2f}")
        
        # Calculate throughput
        if data_size == "small":
            elements_per_call = 10
        elif data_size == "medium":
            elements_per_call = 100
        elif data_size == "large":
            elements_per_call = 1000
        elif data_size == "huge":
            elements_per_call = 10000
        elif data_size == "massive":
            elements_per_call = 100000
        else:
            elements_per_call = 1000
            
        elements_per_second = elements_per_call * (1/avg_time)
        print(f"  Elements/sec: {elements_per_second:,.0f}")
        
        self.results[f"{transport_name}_{data_size}"] = {
            'times': times,
            'average': avg_time,
            'median': median_time,
            'calls_per_second': 1/avg_time,
            'elements_per_second': elements_per_second,
            'data_size': data_size
        }
    
    def compare_results(self):
        """Compare all transport results"""
        print("\n" + "="*60)
        print("SPEED COMPARISON")
        print("="*60)
        
        if len(self.results) < 2:
            print("Need at least 2 transports to compare")
            return
        
        # Sort by average time (fastest first)
        sorted_results = sorted(self.results.items(), key=lambda x: x[1]['average'])
        
        print("Ranking (fastest to slowest):")
        for i, (transport, data) in enumerate(sorted_results, 1):
            print(f"{i}. {transport}: {data['average']:.4f}s avg "
                  f"({data['calls_per_second']:.1f} calls/sec, "
                  f"{data['elements_per_second']:,.0f} elements/sec)")
        
        # Calculate speed differences
        if len(sorted_results) >= 2:
            fastest = sorted_results[0]
            slowest = sorted_results[-1]
            speed_diff = slowest[1]['average'] / fastest[1]['average']
            print(f"\n{fastest[0]} is {speed_diff:.1f}x faster than {slowest[0]}")

async def main():
    """Run the speed tests with different data sizes"""
    tester = SpeedTest()
    
    print("Starting MCP Transport Speed Test")
    print("="*60)
    
    # Configuration
    num_calls = 50  # Increased from 10
    data_sizes = ["huge", "massive"]  # Test with multiple data sizes
    
    for data_size in data_sizes:
        print(f"\n🔄 Testing with {data_size} data size...")
        print(f"📊 Running {num_calls} calls per transport")
        print("-" * 40)
        
        # Test STDIO
        print(f"\nTesting STDIO transport with {data_size} data...")
        stdio_times = await tester.test_stdio(num_calls, data_size)
        tester.analyze_results("STDIO", stdio_times, data_size)
        
        # Wait between tests
        await asyncio.sleep(2)
        
        # Test SSE
        print(f"\nTesting SSE transport with {data_size} data...")
        print("Make sure to run: uv run python server.py --transport sse --port 8080")
        try:
            input("Press Enter when SSE server is ready (or Ctrl+C to skip)...")
            sse_times = await tester.test_sse(num_calls, data_size)
            tester.analyze_results("SSE", sse_times, data_size)
        except KeyboardInterrupt:
            print("Skipping SSE test...")
        
        # Wait between tests
        await asyncio.sleep(2)
        
        # Test Streamable HTTP
        print(f"\nTesting Streamable HTTP transport with {data_size} data...")
        print("Make sure to run: uv run python server.py --transport streamable-http --port 8050")
        try:
            input("Press Enter when HTTP server is ready (or Ctrl+C to skip)...")
            http_times = await tester.test_streamable_http(num_calls, data_size)
            tester.analyze_results("Streamable HTTP", http_times, data_size)
        except KeyboardInterrupt:
            print("Skipping HTTP test...")
    
    # Compare all results
    tester.compare_results()

if __name__ == "__main__":
    asyncio.run(main())