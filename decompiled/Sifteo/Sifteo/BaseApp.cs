using System;
using System.Collections.Generic;
using System.Threading;
using System.Timers;

namespace Sifteo;

public class BaseApp
{
	public delegate void StoppedEventHandler();

	public delegate void PauseEventHandler();

	public delegate void UnpauseEventHandler();

	public delegate void IdleEventHandler();

	private CubeSet mCubeSet;

	private IMsgService mMsgService;

	private System.Timers.Timer tickTimer;

	private AutoResetEvent mTimerEvent = new AutoResetEvent(initialState: false);

	private bool mIsInitialized;

	private bool mIsFinished;

	private static BaseApp instance;

	public SoundSet Sounds { get; private set; }

	public ImageSet Images { get; private set; }

	public Data StoredData { get; private set; }

	public string AppID { get; private set; }

	public bool IsIdle { get; internal set; }

	public virtual int FrameRate => 20;

	public float DeltaTime => 1f / (float)FrameRate;

	public CubeSet CubeSet => mCubeSet;

	internal static BaseApp Instance => instance;

	public event StoppedEventHandler StoppedEvent;

	public event PauseEventHandler PauseEvent;

	public event UnpauseEventHandler UnpauseEvent;

	public event IdleEventHandler IdleEvent;

	public BaseApp()
	{
		if (instance == null)
		{
			instance = this;
		}
		tickTimer = new System.Timers.Timer(1000.0 / (double)FrameRate);
		tickTimer.Elapsed += delegate
		{
			mTimerEvent.Set();
		};
		Sounds = new SoundSet();
		Images = new ImageSet();
		StoredData = new Data();
		mMsgService = new JsonRpcService(this);
		mCubeSet = new CubeSet(mMsgService);
		mMsgService.SetCubeSet(mCubeSet);
		mMsgService.StartListening();
	}

	public void Run()
	{
		mMsgService.Call("app.init", AppInitHandler);
		while (!mIsInitialized)
		{
			if (mMsgService.DataRxWaitHandle.WaitOne())
			{
				mMsgService.HandleDataRx();
			}
		}
		Setup();
		tickTimer.Enabled = true;
		WaitHandle[] array = new WaitHandle[2] { mTimerEvent, mMsgService.DataRxWaitHandle };
		while (!mIsFinished)
		{
			switch (WaitHandle.WaitAny(array))
			{
			case 0:
				Tick();
				break;
			case 1:
				mMsgService.HandleDataRx();
				array[1] = mMsgService.DataRxWaitHandle;
				break;
			}
		}
	}

	private void AppInitHandler(object error, Dictionary<string, object> results)
	{
		if (error != null)
		{
			Log.Error("app init error! {0}", error);
			return;
		}
		foreach (KeyValuePair<string, object> result in results)
		{
			switch (result.Key)
			{
			case "sounds":
			{
				if (!(result.Value is Dictionary<string, object>[] array6))
				{
					break;
				}
				Dictionary<string, object>[] array7 = array6;
				foreach (Dictionary<string, object> dictionary3 in array7)
				{
					if (dictionary3.ContainsKey("name"))
					{
						Sounds.Add((string)dictionary3["name"]);
					}
				}
				break;
			}
			case "images":
			{
				if (!(result.Value is Dictionary<string, object>[] array4))
				{
					break;
				}
				Dictionary<string, object>[] array5 = array4;
				foreach (Dictionary<string, object> dictionary2 in array5)
				{
					if (dictionary2.ContainsKey("name") && dictionary2.ContainsKey("width") && dictionary2.ContainsKey("height"))
					{
						Images.Add(new ImageInfo((string)dictionary2["name"], (int)dictionary2["width"], (int)dictionary2["height"]));
					}
				}
				break;
			}
			case "cubes":
			{
				if (!(result.Value is Dictionary<string, object>[] array))
				{
					break;
				}
				Dictionary<string, object>[] array2 = array;
				foreach (Dictionary<string, object> dictionary in array2)
				{
					if (dictionary.TryGetValue("hardwareID", out var value) && dictionary.TryGetValue("id", out var value2))
					{
						Cube cube = mCubeSet.CubeConnected((int)value2, (string)value);
						if (dictionary.TryGetValue("buttonState", out var value3))
						{
							cube.ButtonIsPressed = (bool)value3;
						}
						if (dictionary.TryGetValue("tiltState", out var value4))
						{
							int[] array3 = value4 as int[];
							cube.SetTiltData(array3[0], array3[1], array3[2]);
						}
					}
				}
				break;
			}
			case "appID":
				AppID = result.Value as string;
				StoredData.SetAppID(AppID);
				break;
			}
		}
		mIsInitialized = true;
	}

	internal void HandleConnected()
	{
	}

	internal void HandleDisconnected()
	{
		Console.WriteLine("disconnected.");
		tickTimer.Enabled = false;
		if (this.StoppedEvent != null)
		{
			this.StoppedEvent();
		}
		mIsFinished = true;
		mMsgService.CancelWaitForData();
	}

	public virtual void Setup()
	{
	}

	public virtual void Tick()
	{
	}

	internal void PauseMsgReceived()
	{
		tickTimer.Enabled = false;
		if (this.PauseEvent != null)
		{
			this.PauseEvent();
		}
	}

	internal void UnpauseMsgReceived()
	{
		if (this.UnpauseEvent != null)
		{
			this.UnpauseEvent();
		}
		tickTimer.Enabled = true;
	}

	internal void LinkEmptyMsgReceived()
	{
		if (!IsIdle)
		{
			IsIdle = true;
			if (this.IdleEvent != null)
			{
				this.IdleEvent();
			}
		}
	}
}
