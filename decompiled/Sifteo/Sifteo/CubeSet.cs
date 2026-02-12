using System;
using System.Collections;
using System.Collections.Generic;

namespace Sifteo;

public class CubeSet : IEnumerable<Cube>, IEnumerable
{
	public delegate bool Predicate(Cube c);

	private IMsgService mMsgService;

	private Dictionary<int, Cube> mCubes = new Dictionary<int, Cube>(6);

	private Dictionary<string, Cube> disconnectedCubes = new Dictionary<string, Cube>();

	private List<Cube> mIndexedCubes = new List<Cube>(6);

	private Dictionary<int, Cube[]> mCoalescedNeighbors = new Dictionary<int, Cube[]>();

	public int Count => mCubes.Count;

	public Cube this[int i] => mIndexedCubes[i];

	public event CubeConnectedHandler NewCubeEvent;

	public event CubeDisconnectedHandler LostCubeEvent;

	public event NeighborEventHandler NeighborAddEvent;

	public event NeighborEventHandler NeighborRemoveEvent;

	public void ClearEvents()
	{
		this.NewCubeEvent = null;
		this.LostCubeEvent = null;
		this.NeighborAddEvent = null;
		this.NeighborRemoveEvent = null;
		foreach (Cube value in mCubes.Values)
		{
			value.ClearEvents();
		}
	}

	public void ClearUserData()
	{
		foreach (Cube value in mCubes.Values)
		{
			value.userData = null;
		}
	}

	internal CubeSet(IMsgService msgService)
	{
		mMsgService = msgService;
	}

	IEnumerator IEnumerable.GetEnumerator()
	{
		return GetEnumerator();
	}

	public IEnumerator<Cube> GetEnumerator()
	{
		return mIndexedCubes.GetEnumerator();
	}

	public bool Contains(Cube c)
	{
		return mCubes.ContainsKey(c.SessionId);
	}

	public Cube[] toArray()
	{
		return mIndexedCubes.ToArray();
	}

	public Cube Find(Predicate p)
	{
		foreach (Cube mIndexedCube in mIndexedCubes)
		{
			if (p(mIndexedCube))
			{
				return mIndexedCube;
			}
		}
		return null;
	}

	public Cube CubeByID(string id)
	{
		foreach (Cube mIndexedCube in mIndexedCubes)
		{
			if (mIndexedCube.UniqueId == id)
			{
				return mIndexedCube;
			}
		}
		return null;
	}

	internal Cube CubeBySessionID(int id)
	{
		mCubes.TryGetValue(id, out var value);
		return value;
	}

	internal Cube CubeConnected(int sessionid, string uniqueid)
	{
		if (!mCubes.ContainsKey(sessionid))
		{
			Cube cube;
			if (disconnectedCubes.ContainsKey(uniqueid))
			{
				cube = disconnectedCubes[uniqueid];
				disconnectedCubes.Remove(uniqueid);
				cube.SessionId = sessionid;
				cube.Orientation = Cube.Side.TOP;
			}
			else
			{
				cube = new Cube(mMsgService, new Cube[4], sessionid, uniqueid);
			}
			mCoalescedNeighbors[sessionid] = cube.Neighbors.BackingArray();
			mCubes[sessionid] = cube;
			mIndexedCubes.Add(cube);
			if (this.NewCubeEvent != null)
			{
				this.NewCubeEvent(cube);
			}
			return cube;
		}
		return null;
	}

	internal void CubeDisconnected(int sessionid)
	{
		if (!mCubes.ContainsKey(sessionid))
		{
			return;
		}
		Cube cube = mCubes[sessionid];
		mCubes.Remove(sessionid);
		mIndexedCubes.Remove(cube);
		mCoalescedNeighbors.Remove(sessionid);
		foreach (KeyValuePair<int, Cube[]> mCoalescedNeighbor in mCoalescedNeighbors)
		{
			for (int i = 0; i < mCoalescedNeighbor.Value.Length; i++)
			{
				if (object.ReferenceEquals(mCoalescedNeighbor.Value[i], cube))
				{
					mCoalescedNeighbor.Value[i] = null;
				}
			}
		}
		cube.Neighbors.Clear();
		cube.ClearPhysicalNeighbors();
		disconnectedCubes.Add(cube.UniqueId, cube);
		if (this.LostCubeEvent != null)
		{
			this.LostCubeEvent(cube);
		}
	}

	internal void NeighborUpdate(int id1, Cube.Side side1, int id2, Cube.Side side2)
	{
		if (mCubes.ContainsKey(id1) && Neighbors.SideIsValid(side1))
		{
			if (id2 == 254)
			{
				HandleNeighborRemove(mCubes[id1], side1);
			}
			else if (mCubes.ContainsKey(id2))
			{
				HandleNeighborAdd(mCubes[id1], side1, mCubes[id2], side2);
			}
		}
	}

	private void HandleNeighborAdd(Cube cube1, Cube.Side side1, Cube cube2, Cube.Side side2)
	{
		if (!Neighbors.SideIsValid(side2) || side1 == Cube.Side.NONE || side2 == Cube.Side.NONE || (cube1.mPhysicalNeighbors[(int)side1] == cube2 && cube2.mPhysicalNeighbors[(int)side2] == cube1))
		{
			return;
		}
		Cube.Side side3 = cube1.Neighbors.CoalescedPhysicalSideOf(cube2);
		if (side3 != Cube.Side.NONE && side3 != side1)
		{
			HandleNeighborRemove(cube2, cube2.Neighbors.CoalescedPhysicalSideOf(cube1), forceRemoveBoth: true);
		}
		side3 = cube2.Neighbors.CoalescedPhysicalSideOf(cube1);
		if (side3 != Cube.Side.NONE && side3 != side2)
		{
			HandleNeighborRemove(cube1, cube2.Neighbors.CoalescedPhysicalSideOf(cube2), forceRemoveBoth: true);
		}
		Cube cube3 = cube1.mPhysicalNeighbors[(int)side1];
		if (cube3 != null && cube3 != cube2)
		{
			HandleNeighborRemove(cube1, side1, forceRemoveBoth: true);
		}
		Cube cube4 = cube2.mPhysicalNeighbors[(int)side2];
		if (cube4 != null && cube4 != cube1)
		{
			HandleNeighborRemove(cube2, side2, forceRemoveBoth: true);
		}
		bool flag = cube1.mPhysicalNeighbors[(int)side1] == null && cube2.mPhysicalNeighbors[(int)side2] == null;
		cube1.NeighborAdd(side1, cube2, side2);
		if (flag)
		{
			mCoalescedNeighbors[cube1.SessionId][(int)side1] = cube2;
			mCoalescedNeighbors[cube2.SessionId][(int)side2] = cube1;
			Cube.Side side4 = cube1.CoalescedNeighborAdd(side1, cube2, side2);
			Cube.Side side5 = cube2.CoalescedNeighborAdd(side2, cube1, side1);
			if (this.NeighborAddEvent != null)
			{
				this.NeighborAddEvent(cube1, side4, cube2, side5);
			}
		}
	}

	private void HandleNeighborRemove(Cube cube, Cube.Side removedFromSide, bool forceRemoveBoth = false)
	{
		if (removedFromSide == Cube.Side.NONE)
		{
			return;
		}
		int num = -1;
		Cube cube2 = cube.mPhysicalNeighbors[(int)removedFromSide];
		if (cube2 == null || !mCoalescedNeighbors.ContainsKey(cube2.SessionId))
		{
			return;
		}
		num = Array.IndexOf(mCoalescedNeighbors[cube2.SessionId], cube);
		if (num < 0 || !Neighbors.SideIsValid((Cube.Side)num))
		{
			return;
		}
		if (!mCoalescedNeighbors.ContainsKey(cube2.SessionId))
		{
			DoRemoveNeighbor(cube, removedFromSide, cube2, (Cube.Side)num);
			return;
		}
		cube.NeighborRemove(removedFromSide, cube2, (Cube.Side)num);
		if (forceRemoveBoth)
		{
			cube2.NeighborRemove((Cube.Side)num, cube, removedFromSide);
		}
		if (cube.mPhysicalNeighbors[(int)removedFromSide] == null && cube2.mPhysicalNeighbors[num] == null)
		{
			DoRemoveNeighbor(cube, removedFromSide, cube2, (Cube.Side)num);
		}
	}

	private void DoRemoveNeighbor(Cube cube1, Cube.Side side1, Cube cube2, Cube.Side side2)
	{
		mCoalescedNeighbors[cube1.SessionId][(int)side1] = null;
		mCoalescedNeighbors[cube2.SessionId][(int)side2] = null;
		Cube.Side side3 = cube1.CoalescedNeighborRemove(side1, cube2, side2);
		Cube.Side side4 = cube2.CoalescedNeighborRemove(side2, cube1, side1);
		if (this.NeighborRemoveEvent != null)
		{
			this.NeighborRemoveEvent(cube1, side3, cube2, side4);
		}
	}
}
