#!/bin/bash
# scripts/deploy_mcp.sh
# Deployment helper for AI Engineering Lab MCP Servers to Cloud Providers (Railway, Fly.io, Google Cloud Run)

set -e

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${BLUE}=== MCP Server Cloud Deployment Helper ===${NC}\n"
echo "Select the target cloud provider:"
echo "1) Railway (Recommended for fast deployments)"
echo "2) Fly.io (Good for edge computing and low-latency stdio/SSE)"
echo "3) Google Cloud Run (Great for enterprise, scale-to-zero serverless)"
echo "4) Show documentation only"
echo ""
read -p "Enter choice [1-4]: " choice

case $choice in
    1)
        echo -e "\n${BLUE}=== Deploying to Railway ===${NC}"
        echo -e "${YELLOW}[Prerequisites] Railway CLI installed and authenticated (run 'railway login')${NC}"
        echo "Railway runs the Dockerfile directly. Let's initialize a Railway project:"
        
        if command -v railway &> /dev/null; then
            railway init
            echo -e "${YELLOW}Set GEMINI_API_KEY as an environment variable in the Railway Dashboard.${NC}"
            echo "Deploying..."
            railway up
            echo -e "${GREEN}✓ Deploy triggered on Railway!${NC}"
        else
            echo -e "${YELLOW}Railway CLI not found. Copy/paste these commands to deploy manually:${NC}"
            echo "  npm i -g @railway/cli"
            echo "  railway login"
            echo "  railway init"
            echo "  railway variables set GEMINI_API_KEY=your_api_key_here"
            echo "  railway up"
        fi
        ;;
    2)
        echo -e "\n${BLUE}=== Deploying to Fly.io ===${NC}"
        echo -e "${YELLOW}[Prerequisites] flyctl CLI installed and authenticated (run 'fly auth login')${NC}"
        
        # Write fly.toml if it does not exist
        if [ ! -f "fly.toml" ]; then
            echo "Generating fly.toml config file..."
            cat <<EOF > fly.toml
app = "ai-mcp-education"
primary_region = "eze"

[build]
  dockerfile = "Dockerfile"

[http_service]
  internal_port = 8000
  force_https = true
  auto_stop_machines = true
  auto_start_machines = true
  min_machines_running = 0
  processes = ["app"]
EOF
            echo -e "${GREEN}✓ Created fly.toml${NC}"
        fi
        
        if command -v flyctl &> /dev/null; then
            fly launch --copy-config --no-deploy
            echo -e "${YELLOW}Secrets configuration:${NC}"
            fly secrets set GEMINI_API_KEY="your_api_key_here"
            echo "Deploying..."
            fly deploy
            echo -e "${GREEN}✓ Deploy triggered on Fly.io!${NC}"
        else
            echo -e "${YELLOW}flyctl CLI not found. Copy/paste these commands to deploy manually:${NC}"
            echo "  curl -L https://fly.io/install.sh | sh"
            echo "  fly auth login"
            echo "  fly launch"
            echo "  fly secrets set GEMINI_API_KEY=your_api_key_here"
            echo "  fly deploy"
        fi
        ;;
    3)
        echo -e "\n${BLUE}=== Deploying to Google Cloud Run ===${NC}"
        echo -e "${YELLOW}[Prerequisites] gcloud SDK installed and authenticated${NC}"
        
        read -p "Enter Google Cloud Project ID: " project_id
        read -p "Enter preferred Region (e.g. us-central1): " region
        
        if [ -n "$project_id" ] && [ -n "$region" ]; then
            echo "Building and pushing container image to Artifact Registry..."
            gcloud builds submit --tag gcr.io/$project_id/mcp-education-server --project $project_id
            
            echo "Deploying to Cloud Run..."
            gcloud run deploy mcp-education-server \
                --image gcr.io/$project_id/mcp-education-server \
                --platform managed \
                --region $region \
                --allow-unauthenticated \
                --set-env-vars GEMINI_API_KEY="your_api_key_here" \
                --project $project_id
                
            echo -e "${GREEN}✓ Successfully deployed to Cloud Run!${NC}"
        else
            echo -e "${YELLOW}Copy/paste these commands to deploy to Cloud Run manually:${NC}"
            echo "  gcloud builds submit --tag gcr.io/YOUR_PROJECT_ID/mcp-education-server"
            echo "  gcloud run deploy mcp-education-server \\"
            echo "    --image gcr.io/YOUR_PROJECT_ID/mcp-education-server \\"
            echo "    --platform managed \\"
            echo "    --region us-central1 \\"
            echo "    --allow-unauthenticated \\"
            echo "    --set-env-vars GEMINI_API_KEY=YOUR_KEY"
        fi
        ;;
    4|*)
        echo -e "\n${BLUE}=== Deployment Documentation ===${NC}"
        echo "Railway:"
        echo "  Railway connects directly to your GitHub repo and deploys using the Dockerfile."
        echo "  Make sure to configure the Port in the Railway service settings to 8000."
        echo ""
        echo "Fly.io:"
        echo "  Use the generated fly.toml. Run 'fly deploy' to start edge machines."
        echo "  The app is configured to scale-to-zero (min_machines_running = 0) when idle."
        echo ""
        echo "Google Cloud Run:"
        echo "  Runs containerized workloads. It scales to zero automatically to save costs."
        echo "  Requires setting '--allow-unauthenticated' if the client needs public access."
        ;;
esac
