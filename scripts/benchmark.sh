# ============================================
# wrk 压测脚本 —— 部署到服务器后执行
# ============================================
# 使用方法：
#   1. 服务器安装 wrk: apt install wrk -y
#   2. chmod +x benchmark.sh && ./benchmark.sh
# ============================================

#!/bin/bash
set -e

BASE_URL="${1:-http://localhost}"
RESULT_DIR="benchmark-results/$(date +%Y%m%d_%H%M%S)"
mkdir -p "$RESULT_DIR"

echo "========================================"
echo "  AI测试平台 压测报告"
echo "  目标: $BASE_URL"
echo "  时间: $(date '+%Y-%m-%d %H:%M:%S')"
echo "  结果目录: $RESULT_DIR"
echo "========================================"
echo ""

# ---- 辅助函数 ----
run_wrk() {
    local name="$1"
    local url="$2"
    local method="${3:-GET}"
    local connections="${4:-10}"
    local duration="${5:-30s}"
    local body="${6:-}"

    echo ">>> 测试: $name"
    echo "    方法: $method | 连接数: $connections | 时长: $duration"

    local output="$RESULT_DIR/${name// /_}.txt"

    if [ -n "$body" ]; then
        wrk -t4 -c"$connections" -d"$duration" \
            -s <(echo "wrk.method = \"$method\"; wrk.body = \"$body\"; wrk.headers[\"Content-Type\"] = \"application/json\"") \
            --latency "$url" | tee "$output"
    else
        wrk -t4 -c"$connections" -d"$duration" --latency "$url" | tee "$output"
    fi
    echo ""
}

# ---- 1. 基础健康检查 ----
echo "=== 1. 健康检查预热 ==="
run_wrk "01-health-check"     "$BASE_URL/api/health/" "GET" 5 10s
run_wrk "02-orchestrator-health" "$BASE_URL/api/v1/health/live" "GET" 5 10s

# ---- 2. 前端静态页面 ----
echo "=== 2. 前端静态页面 ==="
run_wrk "03-frontend-home"    "$BASE_URL/" "GET" 50 30s

# ---- 3. API 接口压测 ----
echo "=== 3. 后端 API ==="
run_wrk "04-testcase-list"    "$BASE_URL/api/testcases/" "GET" 20 30s
run_wrk "05-testsuite-list"   "$BASE_URL/api/testsuites/" "GET" 20 30s
run_wrk "06-report-list"      "$BASE_URL/api/reports/" "GET" 20 30s

# ---- 4. 编排服务 API ----
echo "=== 4. 编排服务 API ==="
run_wrk "07-task-list"        "$BASE_URL/api/v1/tasks/" "GET" 20 30s
run_wrk "08-template-list"    "$BASE_URL/api/v1/templates/" "GET" 20 30s
run_wrk "09-checkpoint-api"   "$BASE_URL/api/v1/workflow/checkpoint/test-task" "GET" 10 20s

# ---- 5. 数据库密集型 ----
echo "=== 5. 数据库读压测 ==="
run_wrk "10-db-read"          "$BASE_URL/api/testcases/?page=1&size=50" "GET" 20 30s

# ---- 6. 极限并发 ----
echo "=== 6. 极限并发 ==="
run_wrk "11-stress-health"    "$BASE_URL/api/health/" "GET" 100 60s
run_wrk "12-stress-frontend"  "$BASE_URL/" "GET" 200 60s

# ---- 7. 生成汇总报告 ----
echo "=== 7. 生成汇总报告 ==="

REPORT="$RESULT_DIR/summary.md"
cat > "$REPORT" << 'EOF'
# AI测试平台 压测报告

## 环境信息

- 服务器：待填（4C16G 阿里云 ECS）
- 测试时间：$(date)
- 数据库：PostgreSQL 16
- 缓存：Redis 7
- 测试工具：wrk (4 threads, variable connections)

## 结果汇总

| 序号 | 测试场景 | 连接数 | QPS | P50 | P99 | 错误数 |
|------|----------|--------|-----|-----|-----|--------|
EOF

for f in "$RESULT_DIR"/*.txt; do
    name=$(basename "$f" .txt | sed 's/^[0-9]*-//')
    qps=$(grep "Requests/sec" "$f" | awk '{print $2}')
    p50=$(grep "50%" "$f" | awk '{print $2}')
    p99=$(grep "99%" "$f" | awk '{print $2}')
    errors=$(grep "Non-2xx" "$f" | awk '{print $3}')
    echo "| $name | - | $qps | $p50 | $p99 | $errors |" >> "$REPORT"
done

echo "" >> "$REPORT"
echo "## 关键发现" >> "$REPORT"
echo "" >> "$REPORT"
echo "(待填写：瓶颈分析、优化建议)" >> "$REPORT"

echo "========================================"
echo "  压测完成！结果保存在: $RESULT_DIR"
echo "  汇总报告: $REPORT"
echo "========================================"
