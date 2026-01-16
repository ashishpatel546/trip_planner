from crewai import Agent, Crew, Process, Task, LLM
from crewai.project import CrewBase, agent, crew, task, before_kickoff, after_kickoff
from crewai.agents.agent_builder.base_agent import BaseAgent
from typing import List, Optional
from crewai_tools import FileWriterTool
from textwrap import dedent
import os
from trip_planner.tools.cached_search_tool import get_cached_search_tool
from trip_planner.tools.flight_search_tool import get_flight_search_tool
from crewai.knowledge.source.string_knowledge_source import StringKnowledgeSource
from pathlib import Path
import queue


@CrewBase
class TripPlanner():
    """TripPlanner crew with optimized configuration"""

    agents: List[BaseAgent]
    tasks: List[Task]
    progress_queue: Optional[queue.Queue] = None  # For real-time progress updates

    @property
    def LLM_MODEL(self):
        return os.getenv("MODEL", "gpt-4o-mini")
    
    @property
    def OpenAIGPT4OMini(self):
        return LLM(
            model=self.LLM_MODEL,
            api_key=os.getenv("OPENAI_API_KEY"),
            temperature=0.3,  # Lower for faster, more focused responses
            timeout=120  # Add timeout to prevent hangs
        )

    def _load_knowledge_sources(self):
        """Load knowledge sources from files"""
        knowledge_dir = Path(__file__).parent.parent.parent / "knowledge"
        sources = []
        
        # Load all text files from knowledge directory
        for file_path in knowledge_dir.glob("*.txt"):
            try:
                content = file_path.read_text(encoding='utf-8')
                sources.append(StringKnowledgeSource(
                    content=content,
                    metadata={"source": file_path.name}
                ))
            except Exception as e:
                print(f"Warning: Could not load {file_path.name}: {e}")
        
        return sources

    @agent
    def city_selection_expert(self) -> Agent:
        """Expert that selects the best city based on criteria"""
        return Agent(
            config=self.agents_config['city_selection_expert'], # type: ignore[index]
            verbose=True,
            tools=[get_cached_search_tool(), get_flight_search_tool()],
            llm=self.OpenAIGPT4OMini,
            max_iter=2,  # Reduced from 5 for speed
        )
    
    @agent
    def local_tour_guide(self) -> Agent:
        """Local expert with deep knowledge of the selected city"""
        return Agent(
            config=self.agents_config['local_tour_guide'], # type: ignore[index]
            verbose=True,
            tools=[get_cached_search_tool()],
            llm=self.OpenAIGPT4OMini,
            max_iter=2,  # Reduced from 5 for speed
        )

    @agent
    def expert_travel_agent(self) -> Agent:
        """Master planner that creates comprehensive itinerary"""
        return Agent(
            config=self.agents_config['expert_travel_agent'], # type: ignore[index]
            verbose=True,
            tools=[FileWriterTool()],  # No search tool - uses context from other agents
            llm=self.OpenAIGPT4OMini,
            max_iter=2,  # Reduced from 3 for speed
        )

    @task
    def city_selection(self) -> Task:
        """Task to select the best city"""
        return Task(
            config=self.tasks_config['city_selection'], # type: ignore[index]
            output_file="reports/city_selection_report.md"  # Save for reuse
        )

    @task
    def local_tour_details(self) -> Task:
        """Task to gather local insights"""
        return Task(
            config=self.tasks_config['local_tour_details'], # type: ignore[index]
            context=[self.city_selection()],  # Uses output from city_selection
            output_file="reports/local_guide_details.md"  # Save for reuse
        )
    
    @task
    def plan_itinerary(self) -> Task:
        """Task to create final itinerary"""
        return Task(
            config=self.tasks_config['plan_itinerary'], # type: ignore[index]
            context=[self.city_selection(), self.local_tour_details()],  # Uses both previous outputs
        )
    
    @before_kickoff
    def prepare_inputs(self, inputs):
        """Prepare inputs before crew starts"""
        
        # Check if inputs are already provided (API mode) or need to be collected (CLI mode)
        if not inputs.get('origin'):
            # CLI Mode - collect inputs interactively
            print("\n" + "="*60)
            print("🌍 WELCOME TO INTELLIGENT TRIP PLANNER 🌍".center(60))
            print("="*60 + "\n")
            
            inputs['origin'] = input(dedent('''
            📍 From which city are you traveling?
            → '''))
            
            inputs['cities'] = input(dedent('''
            🏙️  Which cities are you considering? (comma separated)
            → '''))
            
            inputs['travel_dates'] = input(dedent('''
            📅 What are your travel dates? (e.g., 2026-03-15 to 2026-03-22)
            → '''))
            
            inputs['trip_days'] = input(dedent('''
            ⏱️  How many days are you planning to travel?
            → '''))
            
            inputs['interests'] = input(dedent('''
            🎯 What are your interests? (e.g., food, culture, adventure, beaches)
            → '''))
            
            print("\n" + "-"*60)
            tip_input = input(dedent('''
            💰 Budget consideration (press Enter for default $1000):
            → '''))
            inputs['tip_amount'] = tip_input if tip_input.strip() else "1000"
            
            currency_input = input(dedent('''
            💱 Preferred currency (USD/INR, press Enter for USD):
            → '''))
            inputs['currency'] = currency_input.upper() if currency_input.strip() and currency_input.upper() in ["USD", "INR"] else "USD"
            
            travelers_input = input(dedent('''
            👥 Number of travelers (press Enter for 1):
            → '''))
            inputs['travelers'] = int(travelers_input) if travelers_input.strip() and travelers_input.isdigit() else 1
            
            print("\n" + "="*60)
            print("🚀 Starting your personalized trip planning...".center(60))
            print("="*60 + "\n")
        else:
            # API Mode - inputs already provided
            self._emit_progress("📋 Inputs received, preparing crew...", "system", "info")
            # Set defaults for missing fields
            if 'tip_amount' not in inputs:
                inputs['tip_amount'] = "1000"
            if 'currency' not in inputs:
                inputs['currency'] = "USD"
            if 'travelers' not in inputs:
                inputs['travelers'] = 1
        
        return inputs
    
    @after_kickoff
    def process_results(self, output):
        """Process results after crew finishes"""
        print("\n" + "="*60)
        print("✅ TRIP PLANNING COMPLETED!".center(60))
        print("="*60 + "\n")
        print("📋 Your personalized itinerary has been created!")
        print("📁 Check the 'reports' folder for detailed files.\n")
        return output

    def _emit_progress(self, message: str, agent: str = "", status: str = "info"):
        """Emit progress update to queue"""
        if self.progress_queue:
            try:
                self.progress_queue.put({
                    "message": message,
                    "agent": agent,
                    "status": status,
                    "timestamp": __import__('datetime').datetime.now().isoformat()
                })
            except Exception as e:
                print(f"ERROR: Failed to put to queue: {e}")
                pass  # Queue might be full or closed
    
    def _step_callback(self, step_output):
        """Callback for each step in the crew execution"""
        try:
            # Map task names to friendly messages
            task_messages = {
                "city_selection": "🎯 Analyzing cities and searching for flights",
                "local_tour_details": "📍 Gathering local attractions and tour details",
                "plan_itinerary": "🗓️ Creating your personalized itinerary"
            }
            
            # Extract info from step output
            if hasattr(step_output, 'task'):
                task_name = getattr(step_output.task, 'name', '')
                task_desc = getattr(step_output.task, 'description', '')[:100]
                
                # Use friendly message if available
                if task_name and task_name in task_messages:
                    self._emit_progress(task_messages[task_name], "system", "working")
                elif task_desc:
                    self._emit_progress(f"📝 {task_desc}...", "system", "info")
            
            if hasattr(step_output, 'agent'):
                agent_role = step_output.agent if isinstance(step_output.agent, str) else getattr(step_output.agent, 'role', 'agent')
                self._emit_progress(f"🤖 {agent_role} is working...", agent_role, "working")
                
        except Exception as e:
            print(f"ERROR: _step_callback failed: {e}")
            import traceback
            traceback.print_exc()
            pass  # Don't let callback errors break execution

    @crew
    def crew(self) -> Crew:
        """Creates the TripPlanner crew with optimizations"""
        
        return Crew(
            name="Trip Planner Crew",
            agents=self.agents,
            tasks=self.tasks,
            process=Process.sequential,
            verbose=True,
            planning=False,  # Disabled for 30-60 sec speed boost
            memory=False,  # Disabled to prevent initialization hang
            max_rpm=15,  # Increased slightly for faster execution
            step_callback=self._step_callback if self.progress_queue else None,  # Real-time progress
        )


if __name__ == "__main__":
    trip_crew = TripPlanner().crew()
    results = trip_crew.kickoff()
