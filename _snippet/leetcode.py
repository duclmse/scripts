#!/usr/bin/env python3

import json
import urllib.request
import urllib.error
import argparse
import sys

def get_problem_details(number):
    """Fetch LeetCode problem details by problem number"""
    
    # Validate input
    if number < 1 or number > 5000:
        print(f"Error: Problem number should be between 1 and 5000")
        return None
    
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0"  # Some sites require this
    }

    query = """
    query problemsetQuestionList($categorySlug: String, $limit: Int, $skip: Int, $filters: QuestionListFilterInput) {
      problemsetQuestionList: questionList(categorySlug: $categorySlug limit: $limit skip: $skip filters: $filters) {
        total: totalNum
        questions: data {
          questionFrontendId
          isPaidOnly
          title
          titleSlug
          difficulty
        }
      }
    }
    """

    payload = {
        "query": query.strip(),  # Fixed: just strip whitespace
        "variables": {
            "categorySlug": "",
            "skip": int(number) - 1,
            "limit": 1,
            "filters": {}
        }
    }

    try:
        data = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(
            "https://leetcode.com/graphql",
            data=data,
            headers=headers,
            method='POST'
        )
        
        with urllib.request.urlopen(req, timeout=10) as response:
            result = json.loads(response.read().decode('utf-8'))
            
            # Check if we got valid data
            questions = result.get("data", {}).get("problemsetQuestionList", {}).get("questions", [])
            if not questions:
                print(f"Error: Problem #{number} not found")
                return None
                
            return result
            
    except urllib.error.HTTPError as e:
        print(f"HTTP Error: {e.code} - {e.reason}")
        return None
    except urllib.error.URLError as e:
        print(f"Network Error: {e.reason}")
        return None
    except json.JSONDecodeError:
        print("Error: Invalid JSON response from LeetCode")
        return None
    except Exception as e:
        print(f"Unexpected error: {type(e).__name__}: {e}")
        return None

def display_problem_info(result):
    """Display problem information in a readable format"""
    try:
        questions = result.get("data", {}).get("problemsetQuestionList", {}).get("questions", [])
        if not questions:
            print("No problem data found")
            return
        
        problem = questions[0]
        
        # Display problem info
        print("\n" + "="*60)
        print(f"Problem #{problem.get('questionFrontendId')}: {problem.get('title')}")
        print(f"Difficulty: {problem.get('difficulty', 'Unknown')}")
        print(f"Premium Only: {'Yes' if problem.get('isPaidOnly') else 'No'}")
        print("="*60)
        
        # Display URL
        title_slug = problem.get("titleSlug")
        if title_slug:
            url = f"https://leetcode.com/problems/{title_slug}/"
            print(f"\n🔗 URL: {url}\n")
            
    except Exception as e:
        print(f"Error displaying info: {e}")

def main():
    parser = argparse.ArgumentParser(
        description="Fetch LeetCode problem details by problem number",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s -n 1          # Fetch problem #1 (Two Sum)
  %(prog)s --number 283  # Fetch problem #283
  %(prog)s               # Interactive mode
        """
    )
    parser.add_argument(
        "-n", "--number", 
        type=int, 
        help="LeetCode problem number (e.g., 1 for Two Sum)"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Show full JSON response"
    )
    
    args = parser.parse_args()
    
    # Get problem number
    if args.number is None:
        try:
            number_input = input("LeetCode problem number: ").strip()
            if not number_input:
                print("No number provided. Exiting.")
                return
            number = int(number_input)
        except ValueError:
            print("Error: Please enter a valid number")
            return
        except KeyboardInterrupt:
            print("\nCancelled.")
            return
    else:
        number = args.number
    
    # Fetch problem details
    print(f"Fetching problem #{number}...")
    result = get_problem_details(number)
    
    if result:
        if args.verbose:
            print("\nFull JSON Response:")
            print(json.dumps(result, indent=2))
        
        display_problem_info(result)

if __name__ == "__main__":
    main()