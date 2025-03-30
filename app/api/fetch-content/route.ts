import { NextResponse } from 'next/server'
import { fetchContentRatelimit } from '@/lib/redis'
import { CONFIG } from '@/lib/config'
import { headers } from 'next/headers'
import { sleep } from 'openai/core.mjs'

export async function POST(request: Request) {
  try {
    const body = await request.json()
    const { url } = body

    if (!url) {
      return NextResponse.json({ error: 'URL is required' }, { status: 400 })
    }

    // Only check rate limit if enabled
    if (CONFIG.rateLimits.enabled) {
      const { success } = await fetchContentRatelimit.limit(url)
      if (!success) {
        return NextResponse.json(
          { error: 'Too many requests' },
          { status: 429 }
        )
      }
    }
    try {
      const response = await fetch(`https://r.jina.ai/${encodeURIComponent(url)}`, {
        method: 'GET',
        headers: {
          'X-With-Links-Summary': 'true',
          'Accept': 'application/json', // Added Accept header
        },
      });
      if (!response.ok) {
        console.warn(`Failed to fetch content for ${url}:`, response.status)
        return NextResponse.json(
          { error: 'Failed to fetch content' },
          { status: response.status }
        )
      }

      const jina_output = await response.json()
      console.log('Jina response json:', jina_output)
      const links = await jina_output.data.links
      console.log('Jina response links:', links)
      const mainTitle = jina_output.data.title || ''; // Initialize main title
      const mainContent = jina_output.data.content || ''; // Initialize main content
      let content = `# Main Page: ${mainTitle}\n${mainContent}`
      if (links && typeof links === 'object') {
        // Iterate over the links
        for (const [key, value] of Object.entries(links)) {
          console.log(`Processing link key: ${key}, value: ${value}`);
          // Skip if the value equals the original URL
          if (value === url || value === `${url}/` || value === `${url}/#page`) {
            console.log(`Skipping link as it matches the original URL: ${value}`);
            continue;
          }
          if (value.startsWith(url)) {
            try {
              // Fetch content for the sub-website using Jina
              const subResponse = await fetch(`https://r.jina.ai/${encodeURIComponent(value)}`, {
                method: 'GET',
                headers: {
                  'X-Engine': 'direct',
                  'X-Retain-Images': 'none',
                  'X-Remove-Selector': 'header, a, .class, #id',
                  'X-Token-Budget': '1000',
                  'Accept': 'application/json',
                },
              });

              if (!subResponse.ok) {
                console.log(subResponse);
                console.warn(`Failed to fetch content for sub-website ${value}:`, subResponse.status);
                if (subResponse.status === 429) {
                  console.log('Rate limit exceeded. Skipping this and Sleep for 1 minute...');
                  sleep(60000); // Sleep for 1 min if rate limited
                }
                continue; // Skip this link if fetching fails
              }

              const subJinaOutput = await subResponse.json();
              const subTitle = subJinaOutput.data.title || '';
              const subContent = subJinaOutput.data.content || '';
              // console.log(`Fetched content for sub-website ${value}:`, subContent);

              // Append the sub-content to the main content
              content += `\n\n---\n\n# Sub-Page: ${subTitle}\n${subContent}`;
            } catch (error) {
              console.warn(`Error fetching content for sub-website ${value}:`, error);
            }
          } else {
            console.log(`Skipping link as it does not start with the main URL: ${value}`);
          }
        }
      }
      console.log(`**********************\nJina response main content:\n${content}\n**********************`)
      return NextResponse.json({ content })
    } catch (error) {
      console.warn(`Error fetching content for ${url}:`, error)
      return NextResponse.json(
        { error: 'Failed to fetch content' },
        { status: 500 }
      )
    }
  } catch (error) {
    console.error('Content fetching error:', error)
    return NextResponse.json({ error: 'Invalid request' }, { status: 400 })
  }
}
