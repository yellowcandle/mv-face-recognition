# 🔐 Setting Up Hugging Face Token for Auto-Sync

This guide explains how to set up the `HF_TOKEN` secret in your GitHub repository to enable automatic syncing to Hugging Face Spaces.

## 📋 Prerequisites

1. **Hugging Face Account**: Sign up at [huggingface.co](https://huggingface.co)
2. **GitHub Repository**: This repository with the workflow file
3. **Admin Access**: To your GitHub repository settings

## 🔑 Step 1: Create Hugging Face Token

1. **Go to Hugging Face Settings**:
   - Visit [https://huggingface.co/settings/tokens](https://huggingface.co/settings/tokens)
   - Click "New token"

2. **Configure Token**:
   - **Name**: `GitHub-Auto-Sync` (or any descriptive name)
   - **Type**: Select **"Write"** (important!)
   - **Scopes**: Make sure it includes:
     - ✅ `Read access to contents of all public repos`
     - ✅ `Write access to contents of repos and spaces`

3. **Create and Copy Token**:
   - Click "Generate a token"
   - **⚠️ IMPORTANT**: Copy the token immediately (you won't see it again!)

## 🔧 Step 2: Add Token to GitHub Secrets

1. **Go to Repository Settings**:
   - Navigate to your GitHub repository
   - Click on `Settings` tab
   - Go to `Secrets and variables` → `Actions`

2. **Create New Secret**:
   - Click "New repository secret"
   - **Name**: `HF_TOKEN`
   - **Value**: Paste your Hugging Face token
   - Click "Add secret"

## 🚀 Step 3: Create Hugging Face Space (Optional)

You can create the Space manually or let the workflow create it automatically:

### Option A: Manual Creation
1. Go to [https://huggingface.co/spaces](https://huggingface.co/spaces)
2. Click "Create new Space"
3. **Space name**: `mv-face-recognition`
4. **SDK**: `Gradio`
5. **Visibility**: `Public` (or Private if preferred)
6. Click "Create Space"

### Option B: Automatic Creation
- The workflow will automatically create the Space if it doesn't exist
- Just push to main branch and the workflow will handle it

## 🔄 Step 4: Test the Workflow

1. **Push to Main Branch**:
   ```bash
   git push origin main
   ```

2. **Check Workflow**:
   - Go to your GitHub repository
   - Click on `Actions` tab
   - Look for "Sync to Hugging Face hub" workflow
   - Check the logs for any errors

3. **Verify Space**:
   - Visit `https://huggingface.co/spaces/YOUR_USERNAME/mv-face-recognition`
   - The Space should contain your files and be building

## 🐛 Troubleshooting

### Common Issues:

1. **"Invalid username or password"**:
   - Check that your HF_TOKEN is correctly set in GitHub secrets
   - Verify the token has "Write" permissions
   - Make sure you copied the full token

2. **"You have read access but not the required permissions"**:
   - Your token needs "Write" access
   - Create a new token with proper permissions

3. **Space not found**:
   - Check the Space name in the workflow file
   - Ensure your username is correct in the workflow

4. **Build fails on HF Spaces**:
   - Check the Space logs on HF
   - Verify `requirements.txt` and `packages.txt` are correct
   - Ensure `app.py` is the entry point

### Manual Verification:

Test your token manually:
```bash
# Test if token works
curl -H "Authorization: Bearer YOUR_HF_TOKEN" \
     https://huggingface.co/api/whoami
```

## 📝 Workflow Details

The updated workflow:
- ✅ Creates the Space automatically if it doesn't exist
- ✅ Uses `huggingface_hub` library for reliable sync
- ✅ Copies only essential files for deployment
- ✅ Has fallback mechanisms for error handling
- ✅ Provides detailed logging for debugging

## 🎉 Success!

Once set up correctly, every push to the `main` branch will automatically:
1. Trigger the GitHub Action
2. Sync your code to HF Spaces
3. Build and deploy your Gradio app
4. Make it available at `https://huggingface.co/spaces/YOUR_USERNAME/mv-face-recognition`

---

For more help, check:
- [HF Spaces Documentation](https://huggingface.co/docs/hub/spaces)
- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [Gradio on HF Spaces](https://huggingface.co/docs/hub/spaces-sdks-gradio)