using System;
using System.Collections.Generic;

namespace Sifteo.Util;

public class StateMachine
{
	private struct StateTransition
	{
		public string state;

		public string transition;

		public StateTransition(string s, string t)
		{
			state = s;
			transition = t;
		}
	}

	private class Lock : IDisposable
	{
		private StateMachine mMachine;

		private bool mLocked = true;

		public Lock(StateMachine sm)
		{
			mMachine = sm;
			mMachine.LockTransitions();
		}

		public void Dispose()
		{
			if (mLocked)
			{
				Log.Info("Disposing of lock for state: " + mMachine.mCurrent);
				mMachine.UnlockTransitions();
				mLocked = false;
			}
			else
			{
				Log.Warning("Attempting to Dispose() lock multiple times, ignoring");
			}
		}
	}

	public delegate string StateFunction(string transitionId);

	private string mCurrent = "";

	private Dictionary<string, IStateController> mStates = new Dictionary<string, IStateController>();

	private Dictionary<StateTransition, string> mTransitions = new Dictionary<StateTransition, string>();

	private int mTransitionMutex = 1;

	private Queue<string> mTransitionQueue = new Queue<string>();

	public IStateController CurrentState => mStates[mCurrent];

	public string Current => mCurrent;

	public StateMachine State(string name, IStateController scene)
	{
		if (!mStates.ContainsKey(name))
		{
			mStates.Add(name, scene);
		}
		return this;
	}

	public StateMachine State(string name, StateFunction func)
	{
		return State(name, new SimpleState(this, func));
	}

	public StateMachine Transition(string fromState, string transitionId, string toState)
	{
		StateTransition key = new StateTransition(fromState, transitionId);
		if (!mTransitions.ContainsKey(key))
		{
			mTransitions.Add(key, toState);
		}
		return this;
	}

	public StateMachine SetState(string name, string transitionId = "")
	{
		if (mTransitionMutex > 0 && mCurrent.Length > 0)
		{
			Log.Warning("Forcing state to [ {0} ], which may cause inconsistent control flow. Recommend using QueueTransition()", name);
		}
		if (mStates.ContainsKey(name))
		{
			Log.Info("Setting State: " + name);
			LockTransitions();
			if (mCurrent.Length > 0)
			{
				mStates[mCurrent].OnDispose();
			}
			mCurrent = name;
			if (mCurrent.Length > 0)
			{
				mStates[mCurrent].OnSetup(transitionId);
			}
			UnlockTransitions();
			CheckTransitionQueue();
		}
		else
		{
			Log.Warning("Attempting to set invalid state [ {0} ], ignoring", name);
		}
		return this;
	}

	public void QueueTransition(string name)
	{
		if (mTransitionMutex > 0)
		{
			mTransitionQueue.Enqueue(name);
			return;
		}
		StateTransition key = new StateTransition(mCurrent, name);
		Log.Info("Applying Transition: " + name);
		if (mTransitions.ContainsKey(key))
		{
			SetState(mTransitions[key], name);
		}
	}

	public void Tick(float dt)
	{
		if (mCurrent.Length > 0)
		{
			CheckTransitionQueue();
			mStates[mCurrent].OnTick(dt);
			CheckTransitionQueue();
		}
	}

	public void Paint(bool canvasDirty)
	{
		if (mCurrent.Length > 0)
		{
			CheckTransitionQueue();
			mStates[mCurrent].OnPaint(canvasDirty);
			CheckTransitionQueue();
		}
	}

	public IDisposable AquireLock()
	{
		Log.Info("Aquiring Lock for State: " + mCurrent);
		return new Lock(this);
	}

	private void LockTransitions()
	{
		mTransitionMutex++;
	}

	private void UnlockTransitions()
	{
		mTransitionMutex--;
		if (mTransitionMutex == 0 && mTransitionQueue.Count > 0)
		{
			QueueTransition(mTransitionQueue.Dequeue());
		}
	}

	private void CheckTransitionQueue()
	{
		UnlockTransitions();
		LockTransitions();
	}
}
