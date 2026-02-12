using System;
using System.Collections.Generic;
using System.Threading;

namespace Sifteo;

internal class JsonRpcService : IMsgService
{
	private JsonRpcConnector mConnector;

	private int mOutgoingMsgID;

	private CubeSet mCubeSet;

	private BaseApp mBaseApp;

	private Dictionary<int, MsgServiceResponseHandler> mResponseHandlers = new Dictionary<int, MsgServiceResponseHandler>();

	private static JsonRpcService instance;

	public static IMsgService Instance => instance;

	public WaitHandle DataRxWaitHandle => mConnector.DataRxWaitHandle;

	public JsonRpcService(BaseApp app)
	{
		if (instance == null)
		{
			instance = this;
		}
		mBaseApp = app;
		mConnector = new JsonRpcConnector(this);
	}

	public void SetCubeSet(CubeSet cs)
	{
		mCubeSet = cs;
	}

	public void Call(string method, MsgServiceResponseHandler res, params object[] args)
	{
		if (res != null)
		{
			mResponseHandlers.Add(mOutgoingMsgID, res);
		}
		Dictionary<string, object> dictionary = new Dictionary<string, object>();
		dictionary["method"] = method;
		if (args.Length > 0)
		{
			dictionary["params"] = args;
		}
		dictionary["id"] = mOutgoingMsgID++;
		lock (mConnector)
		{
			mConnector.Send(dictionary);
			if (method.StartsWith("cube."))
			{
				mBaseApp.IsIdle = false;
			}
		}
	}

	public void StartListening()
	{
		mConnector.StartListening();
	}

	public void HandleDataRx()
	{
		mConnector.HandleDataRx();
	}

	public void CancelWaitForData()
	{
		mConnector.CancelWaitForData();
	}

	internal void HandleConnection()
	{
		mBaseApp.HandleConnected();
	}

	internal void HandleDisconnection()
	{
		mBaseApp.HandleDisconnected();
	}

	internal void OnJsonMsgRxed(Dictionary<string, object> msg)
	{
		if (msg.ContainsKey("result") && msg.ContainsKey("id"))
		{
			int key = (int)msg["id"];
			if (mResponseHandlers.ContainsKey(key))
			{
				mResponseHandlers[key](msg["error"], msg["result"] as Dictionary<string, object>);
				mResponseHandlers.Remove(key);
			}
		}
		else
		{
			if (msg.ContainsKey("error") && msg["error"] != null)
			{
				return;
			}
			if (!msg.ContainsKey("method") || !msg.ContainsKey("id"))
			{
				Console.WriteLine("JsonIncomingMsgCompleteHandler: missing method or params...");
				return;
			}
			switch (msg["method"] as string)
			{
			case "cube.tiltEvent":
			{
				int[] array6 = msg["params"] as int[];
				if (array6.Length >= 4)
				{
					mCubeSet.CubeBySessionID(array6[0])?.SetTiltData(array6[1], array6[2], array6[3]);
				}
				break;
			}
			case "cube.shakeEvent":
			{
				object[] array3 = msg["params"] as object[];
				if (array3.Length >= 3)
				{
					mCubeSet.CubeBySessionID((int)array3[0])?.SetShakeState((bool)array3[1], (int)array3[2]);
				}
				break;
			}
			case "cube.buttonEvent":
			{
				object[] array8 = msg["params"] as object[];
				if (array8.Length >= 2)
				{
					Cube cube = mCubeSet.CubeBySessionID((int)array8[0]);
					if (cube != null)
					{
						cube.ButtonIsPressed = (bool)array8[1];
					}
				}
				break;
			}
			case "cube.neighborEvent":
			{
				int[] array5 = msg["params"] as int[];
				if (array5.Length >= 4)
				{
					mCubeSet.NeighborUpdate(array5[0], (Cube.Side)array5[1], array5[2], (Cube.Side)array5[3]);
				}
				break;
			}
			case "cube.connectedEvent":
			{
				object[] array2 = msg["params"] as object[];
				if (array2.Length > 1)
				{
					mCubeSet.CubeConnected((int)array2[0], (string)array2[1]);
				}
				break;
			}
			case "cube.disconnectedEvent":
			{
				int[] array7 = msg["params"] as int[];
				if (array7.Length > 0)
				{
					mCubeSet.CubeDisconnected(array7[0]);
				}
				break;
			}
			case "app.pauseEvent":
				mBaseApp.PauseMsgReceived();
				break;
			case "app.resumeEvent":
				mBaseApp.UnpauseMsgReceived();
				break;
			case "sound.stoppedEvent":
				if (msg["params"] is int[] array4 && array4.Length >= 1)
				{
					mBaseApp.Sounds.HandleSoundStopped(array4[0]);
				}
				break;
			case "sound.startedEvent":
				if (msg["params"] is int[] array && array.Length > 0)
				{
					mBaseApp.Sounds.HandleSoundStarted(array[0]);
				}
				break;
			case "link.emptyEvent":
				mBaseApp.LinkEmptyMsgReceived();
				break;
			}
		}
	}
}
