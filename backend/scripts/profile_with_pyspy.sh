#!/bin/bash
# Profile the running backend with py-spy
# Usage: ./scripts/profile_with_pyspy.sh

set -e

PID=$(pgrep -f "uvicorn backend.main" | head -1)

if [ -z "$PID" ]; then
    echo "❌ Backend process not found. Start it first."
    exit 1
fi

echo "🔥 Profiling backend (PID: $PID) for 30 seconds..."
echo "   This is non-intrusive (uses ptrace, <5% overhead)"

# Install py-spy if not present
if ! command -v py-spy &> /dev/null; then
    echo "📦 Installing py-spy..."
    pip install py-spy
fi

mkdir -p profiles

# CPU flame graph
echo ""
echo "📊 Generating CPU flame graph..."
py-spy record \
    --pid $PID \
    --output profiles/cpu_flamegraph.svg \
    --format speedscope \
    --duration 30 \
    --rate 100

echo "✅ CPU profile saved: profiles/cpu_flamegraph.svg"

# Memory allocation tracking
echo ""
echo "💾 Capturing memory snapshot..."
py-spy dump \
    --pid $PID \
    > profiles/memory_dump.txt

echo "✅ Memory dump saved: profiles/memory_dump.txt"

# Live top-like view (5 seconds)
echo ""
echo "🖥️  Live process view (5 sec)..."
py-spy top --pid $PID --duration 5 || true

echo ""
echo "✅ Profiling complete!"
echo ""
echo "📁 Generated files:"
ls -la profiles/
