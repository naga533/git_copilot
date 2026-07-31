# Inactive Branch Detection Agent

An AI-powered agent that monitors GitHub repositories to identify and manage feature branches that have been inactive for more than 30 days.

## Features

✅ **Automatic Branch Analysis** - Scans all feature branches and calculates inactivity periods  
✅ **Inactive Detection** - Identifies branches with no commits for 30+ days  
✅ **AI-Powered Decisions** - Uses Claude AI to analyze patterns and recommend actions  
✅ **Issue Creation** - Automatically creates GitHub issues for stale branches  
✅ **Detailed Reports** - Provides comprehensive activity summaries and author information  

## How It Works

```
┌─────────────────────┐
│   User Prompt       │
│ "Analyze stale      │
│  branches"          │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────────────────────────┐
│   Inactive Branch Agent (Claude AI)     │
│                                         │
│ - Receives user request                 │
│ - Decides which tools to use            │
│ - Processes results intelligently       │
└──────────┬──────────────────────────────┘
           │
      ┌────┴────┐
      │          │
      ▼          ▼
  ┌────────────────────────────┐    ┌──────────────────────┐
  │ Analyze Branches Tool      │    │ Create Issue Tool    │
  │                            │    │                      │
  │ - Fetches all branches     │    │ - Creates GitHub     │
  │ - Calculates inactivity    │    │   issue for stale    │
  │ - Returns JSON data        │    │   branches           │
  └────────────────────────────┘    └──────────────────────┘
           │                              │
           └──────────────┬───────────────┘
                          │
                          ▼
              ┌───────────────────────┐
              │   Agent Reasoning     │
              │                       │
              │ Uses AI to:           │
              │ - Interpret results   │
              │ - Make decisions      │
              │ - Create summaries    │
              └───────────┬───────────┘
                          │
                          ▼
                  ┌──────────────────┐
                  │  Final Response  │
                  │                  │
                  │ Reports & Actions│
                  └──────────────────┘
```

## Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/naga533/git_copilot.git
   cd git_copilot
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your credentials
   ```

## Configuration

### Environment Variables

```env
GITHUB_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxx
ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxxxxxxxx
REPOSITORY=owner/repo_name
INACTIVE_DAYS_THRESHOLD=30
AUTO_CREATE_ISSUES=true
```

**Required:**
- `GITHUB_TOKEN`: GitHub Personal Access Token with repo access
  - Create at: https://github.com/settings/tokens
  - Required scopes: `repo`, `read:org`

- `ANTHROPIC_API_KEY`: Anthropic API key for Claude AI
  - Get it from: https://console.anthropic.com

## Usage

### Basic Usage

```python
from agents.inactive_branch_agent import InactiveBranchAgent

# Initialize agent
agent = InactiveBranchAgent("owner/repo_name")

# Run analysis
result = agent.run(
    """
    Find all branches inactive for more than 30 days.
    Create issues for branches inactive for more than 60 days.
    """
)

print(result)
```

### Example Prompts

**1. Get Summary of All Branches**
```
Analyze the repository and provide a summary of all branches, 
showing their last commit date and days of inactivity.
```

**2. Identify Stale Branches**
```
Find branches that have been inactive for more than 30 days. 
List them with author, last commit message, and recommendation for action.
```

**3. Create Issues for Very Old Branches**
```
For any branches inactive for more than 60 days, create a GitHub issue 
to alert the team about the stale branch.
```

**4. Comprehensive Analysis**
```
Perform a complete analysis of all feature branches:
1. Identify inactive branches (30+ days)
2. Group them by inactivity duration
3. Recommend cleanup actions
4. Create issues for branches inactive for 90+ days
```

## Tools Available

### 1. `analyze_branches`
Analyzes branch activity and returns detailed information.

**Parameters:**
- `action` (required): 
  - `summary`: Get all branches and their activity
  - `inactive_only`: Get only branches inactive for 30+ days

**Returns:**
```json
{
  "repository": "owner/repo",
  "total_branches": 5,
  "inactive_branches_count": 2,
  "branches": [
    {
      "name": "feature/old-feature",
      "last_commit": "2026-05-15T10:30:00",
      "days_inactive": 77,
      "author": "John Doe",
      "message": "Add feature implementation",
      "status": "inactive"
    }
  ]
}
```

### 2. `create_issue`
Creates a GitHub issue for a stale branch.

**Parameters:**
- `branch_name` (required): Name of the branch
- `days_inactive` (required): Days inactive
- `author` (optional): Last commit author

**Returns:**
```json
{
  "success": true,
  "issue_url": "https://github.com/owner/repo/issues/123",
  "issue_number": 123
}
```

## Architecture

### Classes

**`GitHubBranchAnalyzer`**
- Connects to GitHub API
- Analyzes branch activity
- Calculates inactivity periods

**`Tool` (Abstract Base Class)**
- Base class for agent tools
- Defines tool execution interface

**`AnalyzeBranchesTool`**
- Fetches and analyzes branch data
- Returns structured analysis results

**`CreateIssueForStaleBranchTool`**
- Creates GitHub issues
- Notifies team members

**`InactiveBranchAgent`**
- Orchestrates the analysis
- Uses Claude AI for decision-making
- Manages tool execution
- Maintains conversation history

## Workflow

1. **Initialization**: Agent connects to GitHub and Anthropic APIs
2. **User Request**: Agent receives analysis prompt
3. **Tool Selection**: Claude AI decides which tools to use
4. **Analysis**: Tools gather branch data from GitHub
5. **AI Processing**: Claude analyzes results and makes decisions
6. **Actions**: Agent executes recommended actions (create issues, etc.)
7. **Report**: Agent provides human-readable summary

## Example Output

```
Agent Response:

I've completed the analysis of the git_copilot repository. Here are the findings:

## Repository Overview
- Total Branches: 3
- Inactive Branches (30+ days): 2

## Inactive Branches Detected

### 1. feature_branch_1
- **Days Inactive:** 45
- **Last Commit:** 2026-06-15 (July 31 reference)
- **Author:** Developer Name
- **Last Message:** "Add feature implementation"
- **Status:** ⚠️ STALE - Needs attention
- **Recommendation:** Review and merge or archive

### 2. feature_branch_2
- **Days Inactive:** 35
- **Last Commit:** 2026-06-25
- **Author:** Another Developer
- **Last Message:** "WIP: Ongoing work"
- **Status:** ⚠️ STALE - In progress
- **Recommendation:** Contact author or rebase on main

## Actions Taken
✅ Created GitHub issue for branches inactive 60+ days
✅ Generated cleanup recommendations

## Next Steps
1. Review inactive branches with team
2. Merge completed features to main
3. Archive or delete branches no longer needed
4. Update branch naming conventions if needed
```

## Advanced Usage

### Custom Threshold
```python
# Analyze with custom threshold (60 days)
result = agent.run(
    "Find branches inactive for more than 60 days"
)
```

### Scheduled Monitoring
```python
import schedule
import time

def check_branches():
    agent = InactiveBranchAgent("owner/repo")
    result = agent.run("Analyze inactive branches")
    # Log or notify about results

# Run daily
schedule.every().day.at("09:00").do(check_branches)

while True:
    schedule.run_pending()
    time.sleep(60)
```

### Integration with CI/CD
```yaml
# GitHub Actions Workflow
name: Weekly Branch Audit
on:
  schedule:
    - cron: '0 9 * * 1'  # Every Monday

jobs:
  audit:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Run Branch Audit
        run: |
          pip install -r requirements.txt
          python -m agents.inactive_branch_agent
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
```

## Troubleshooting

### Issue: "Authentication failed"
- **Solution:** Check `GITHUB_TOKEN` and `ANTHROPIC_API_KEY` are correctly set
- Verify tokens have required permissions

### Issue: "Rate limit exceeded"
- **Solution:** GitHub API has rate limits (5000 requests/hour for authenticated requests)
- Implement caching or run less frequently

### Issue: "Branch not found"
- **Solution:** Ensure branch names are correct
- Some branches may be deleted between checks

## Best Practices

1. **Schedule Regularly** - Run weekly or bi-weekly for best results
2. **Review Before Action** - Always review AI recommendations before deleting branches
3. **Document Decisions** - Keep records of archived/deleted branches
4. **Team Communication** - Create issues and notify team before cleanup
5. **Gradual Adoption** - Start with analysis-only, then enable auto-issue creation

## Security Considerations

- ✅ Store tokens in `.env` file (never commit to version control)
- ✅ Use GitHub Personal Access Tokens with minimal required scopes
- ✅ Rotate tokens periodically
- ✅ Review created issues before publishing
- ✅ Keep API keys secure and never share

## Future Enhancements

- [ ] Email notifications for inactive branches
- [ ] Slack integration for team alerts
- [ ] Automatic branch deletion with approval workflow
- [ ] Branch metrics dashboard
- [ ] Commit activity predictions
- [ ] Team productivity analytics

## License

MIT

## Support

For issues or questions:
1. Check GitHub Issues: https://github.com/naga533/git_copilot/issues
2. Create a new issue with details
3. Include agent logs and error messages

---

**Created:** 2026-07-31  
**Agent Type:** AI-Powered Branch Management  
**Framework:** Claude AI + GitHub API
