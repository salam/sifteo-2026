using System.Threading;

namespace Sifteo;

internal interface IMsgService
{
	WaitHandle DataRxWaitHandle { get; }

	void StartListening();

	void Call(string method, MsgServiceResponseHandler res, params object[] args);

	void SetCubeSet(CubeSet cubeset);

	void HandleDataRx();

	void CancelWaitForData();
}
