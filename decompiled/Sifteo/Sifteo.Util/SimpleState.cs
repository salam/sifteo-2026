namespace Sifteo.Util;

internal class SimpleState : IStateController
{
	private StateMachine mMachine;

	private StateMachine.StateFunction mFunc;

	internal SimpleState(StateMachine machine, StateMachine.StateFunction func)
	{
		mMachine = machine;
		mFunc = func;
	}

	void IStateController.OnSetup(string transitionId)
	{
		mMachine.QueueTransition(mFunc(transitionId));
	}

	void IStateController.OnTick(float dt)
	{
	}

	void IStateController.OnPaint(bool canvasDirty)
	{
	}

	void IStateController.OnDispose()
	{
	}
}
